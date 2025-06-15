import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

class PettyCashVoucher(Document):
    def validate(self):
        self.calculate_totals()
        self.set_default_cost_centers()
        self.ensure_cash_supplier_exists()

    def calculate_totals(self):
        self.total = sum(flt(row.debit) for row in self.petty_cash_details)
        self.total_vat = sum(flt(row.amount) for row in self.vat_details)
        self.amount = self.total + self.total_vat + flt(self.items_total)

        frappe.msgprint(f"Calculated Totals:\n- Petty Cash Total: {self.total}\n- VAT: {self.total_vat}\n- Items Total: {self.items_total}\n- Grand Amount: {self.amount}")

    def set_default_cost_centers(self):
        default_cc = frappe.db.get_value("Company", self.company, "cost_center")
        for row in self.petty_cash_details:
            if not row.cost_center:
                row.cost_center = default_cc

    def ensure_cash_supplier_exists(self):
        supplier_name = "Cash Supplier"
        if not frappe.db.exists("Supplier", supplier_name):
            supplier_doc = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier_name,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Company"
            })
            supplier_doc.insert(ignore_permissions=True)
            frappe.msgprint(f"Created supplier: {supplier_name}")

    def on_submit(self):
        self.create_purchase_documents()
        self.make_gl_entries(cancel=False)

    def on_cancel(self):
        self.cancel_purchase_documents()
        self.make_gl_entries(cancel=True)

    def create_purchase_documents(self):
        if not self.petty_cash_items:
            return

        valid_items = []
        for row in self.petty_cash_items:
            if not row.item_code or not row.warehouse:
                frappe.msgprint(f"Skipping item {row.item_code or '[missing code]'} — missing required fields.")
                continue
            valid_items.append(row)

        if not valid_items:
            return

        purchase_receipt = self.create_purchase_receipt(valid_items)
        if purchase_receipt:
            self.create_purchase_invoice(purchase_receipt, valid_items)

    def create_purchase_receipt(self, items):
        try:
            pr_doc = frappe.get_doc({
                "doctype": "Purchase Receipt",
                "supplier": "Cash Supplier",
                "company": self.company,
                "posting_date": self.posting_date,
                "items": []
            })

            for item in items:
                pr_doc.append("items", {
                    "item_code": item.item_code,
                    "qty": flt(item.qty),
                    "rate": flt(item.rate),
                    "amount": flt(item.amount),
                    "warehouse": item.warehouse,
                    "cost_center": item.cost_center or frappe.db.get_value("Company", self.company, "cost_center")
                })

            pr_doc.insert(ignore_permissions=True)
            pr_doc.submit()

            frappe.msgprint(f"Purchase Receipt {pr_doc.name} created successfully")
            self.db_set("purchase_receipt", pr_doc.name)
            return pr_doc

        except Exception as e:
            frappe.throw(f"Error creating Purchase Receipt: {str(e)}")

    def create_purchase_invoice(self, purchase_receipt, items):
        try:
            pi_doc = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": "SUP-0140",
                "company": self.company,
                "posting_date": self.posting_date,
                "items": []
            })

            for i, item in enumerate(items):
                pi_doc.append("items", {
                    "item_code": item.item_code,
                    "qty": flt(item.qty),
                    "rate": flt(item.rate),
                    "amount": flt(item.amount),
                    "warehouse": item.warehouse,
                    "cost_center": item.cost_center or frappe.db.get_value("Company", self.company, "cost_center"),
                    "purchase_receipt": purchase_receipt.name,
                    "pr_detail": purchase_receipt.items[i].name
                })

            pi_doc.insert(ignore_permissions=True)
            pi_doc.submit()

            frappe.msgprint(f"Purchase Invoice {pi_doc.name} created successfully")
            self.db_set("purchase_invoice", pi_doc.name)

            # Create and submit Payment Entry
            payment_entry = get_payment_entry("Purchase Invoice", pi_doc.name)
            payment_entry.posting_date = self.posting_date
            payment_entry.paid_from = self.account_paid_from
            payment_entry.reference_no = self.name
            payment_entry.reference_date = self.posting_date
            payment_entry.insert(ignore_permissions=True)
            payment_entry.submit()

            frappe.msgprint(f"Payment Entry {payment_entry.name} created and submitted against {pi_doc.name}")

        except Exception as e:
            frappe.throw(f"Error creating Purchase Invoice or Payment Entry: {str(e)}")

    def cancel_purchase_documents(self):
        if hasattr(self, 'purchase_invoice') and self.purchase_invoice:
            try:
                pi_doc = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
                if pi_doc.docstatus == 1:
                    pi_doc.cancel()
                    frappe.msgprint(f"Cancelled Purchase Invoice {self.purchase_invoice}")
            except Exception as e:
                frappe.msgprint(f"Error cancelling Purchase Invoice: {str(e)}")

        if hasattr(self, 'purchase_receipt') and self.purchase_receipt:
            try:
                pr_doc = frappe.get_doc("Purchase Receipt", self.purchase_receipt)
                if pr_doc.docstatus == 1:
                    pr_doc.cancel()
                    frappe.msgprint(f"Cancelled Purchase Receipt {self.purchase_receipt}")
            except Exception as e:
                frappe.msgprint(f"Error cancelling Purchase Receipt: {str(e)}")

    def make_gl_entries(self, cancel=False):
        if self.is_purchase:
            frappe.msgprint("Skipping GL Entries — handled via Purchase Invoice and Payment Entry.")
            return

        gl_entries = []

        for row in self.petty_cash_details:
            if not row.expense_account:
                frappe.throw("Expense Account is required in Petty Cash Details.")
            if not row.cost_center:
                frappe.throw("Cost Center is required in Petty Cash Details.")

            gl_entries.append(self.get_gl_dict({
                "account": row.expense_account,
                "party_type": row.party_type,
                "party": row.party,
                "debit": flt(row.debit),
                "debit_in_account_currency": flt(row.debit),
                "against": self.account_paid_from,
                "remarks": row.user_remarks,
                "cost_center": row.cost_center,
                "project": row.project
            }, row=row))

        for vat in self.vat_details:
            if not vat.vat_account:
                frappe.throw("VAT Account is required in VAT Details.")
            gl_entries.append(self.get_gl_dict({
                "account": vat.vat_account,
                "debit": flt(vat.amount),
                "debit_in_account_currency": flt(vat.amount),
                "against": self.account_paid_from,
                "remarks": "VAT Entry"
            }))

        total_debits = sum(flt(d.get("debit", 0)) for d in gl_entries)
        frappe.msgprint(f"Total Debits Collected: {total_debits}\nExpected Amount: {self.amount}")

        if flt(self.amount) > 0:
            against_accounts = []
            against_accounts += [row.expense_account for row in self.petty_cash_details if row.expense_account]
            against_accounts += [vat.vat_account for vat in self.vat_details if vat.vat_account]

            gl_entries.append(self.get_gl_dict({
                "account": self.account_paid_from,
                "credit": flt(self.amount),
                "credit_in_account_currency": flt(self.amount),
                "against": ", ".join(set(filter(None, against_accounts))),
                "remarks": "Paid from Petty Cash Account"
            }))

        total_credits = sum(flt(d.get("credit", 0)) for d in gl_entries)
        frappe.msgprint(f"Final GL Entry Balancing:\n- Total Debits: {total_debits}\n- Total Credits: {total_credits}")

        make_gl_entries(gl_entries, cancel=cancel, update_outstanding='No')

    def get_gl_dict(self, args, row=None):
        account_currency = get_account_currency(args.get("account"))
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

        return frappe._dict({
            "posting_date": self.posting_date,
            "company": self.company,
            "account": args.get("account"),
            "party_type": args.get("party_type"),
            "party": args.get("party"),
            "debit": args.get("debit", 0),
            "credit": args.get("credit", 0),
            "debit_in_account_currency": args.get("debit_in_account_currency", 0),
            "credit_in_account_currency": args.get("credit_in_account_currency", 0),
            "against": args.get("against"),
            "cost_center": args.get("cost_center") or (getattr(row, "cost_center", None) if row else None),
            "project": args.get("project") or (getattr(row, "project", None) if row else None),
            "remarks": args.get("remarks") or self.remarks or "Petty Cash Voucher",
            "account_currency": account_currency,
            "voucher_type": self.doctype,
            "voucher_no": self.name,
            "posting_time": nowdate(),
            "is_opening": "No"
        })