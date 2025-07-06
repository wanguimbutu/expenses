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
        self.get_cash_supplier_id()

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

    def get_cash_supplier_id(self):
        if hasattr(self, "cash_supplier_id") and self.cash_supplier_id:
            return self.cash_supplier_id

        supplier_name = "Cash Supplier"
        supplier_id = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
        if not supplier_id:
            supplier_doc = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier_name,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Company"
            })
            supplier_doc.insert(ignore_permissions=True)
            frappe.msgprint(f"Created supplier: {supplier_doc.name}")
            self.cash_supplier_id = supplier_doc.name
        else:
            self.cash_supplier_id = supplier_id

        return self.cash_supplier_id


    def get_vat_tax_details_from_item(self, item_code):
        """Returns a list of VAT rows with account_head (from tax_type) and rate."""
        tax_template_links = frappe.get_all(
            "Item Tax",
            filters={"parent": item_code, "parenttype": "Item"},
            fields=["item_tax_template"]
        )

        vat_taxes = []

        for row in tax_template_links:
            tax_template = row.item_tax_template
            if not tax_template:
                continue

            tax_details = frappe.get_all(
                "Item Tax Template Detail",
                filters={"parent": tax_template},
                fields=["tax_type", "tax_rate"]
            )

            for tax in tax_details:

                if "VAT" in (tax.tax_type or "").upper():
                    account_head = tax.tax_type  

                    if not account_head:
                        frappe.throw(
                            f"Missing VAT account in Item Tax Template '{tax_template}'."
                        )

                    vat_taxes.append({
                        "account_head": account_head,
                        "rate": flt(tax.tax_rate)
                    })

        return vat_taxes


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
            supplier_id = self.get_cash_supplier_id()
            pr_doc = frappe.get_doc({
                "doctype": "Purchase Receipt",
                "supplier": supplier_id,
                "company": self.company,
                "posting_date": self.posting_date,
                "items": [],
                "taxes": []
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

            added_vat_keys = set()
            for item in items:
                vat_rows = self.get_vat_tax_details_from_item(item.item_code)
                for vat in vat_rows:
                    key = (vat["account_head"], vat["rate"])
                    if key in added_vat_keys:
                        continue
                    added_vat_keys.add(key)

                    pr_doc.append("taxes", {
                        "charge_type": "On Net Total",
                        "account_head": vat["account_head"],
                        "description": "VAT",
                        "rate": vat["rate"],
                        "included_in_print_rate": 1
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
            supplier_id = self.get_cash_supplier_id()
            pi_doc = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": supplier_id,
                "company": self.company,
                "posting_date": self.posting_date,
                "bill_no": self.name,
                "bill_date": self.posting_date,
                "items": [],
                "taxes": []
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

            added_vat_keys = set()
            for item in items:
                vat_rows = self.get_vat_tax_details_from_item(item.item_code)
                for vat in vat_rows:
                    key = (vat["account_head"], vat["rate"])
                    if key in added_vat_keys:
                        continue
                    added_vat_keys.add(key)

                    pi_doc.append("taxes", {
                        "charge_type": "On Net Total",
                        "account_head": vat["account_head"],
                        "description": "VAT",
                        "rate": vat["rate"],
                        "included_in_print_rate": 1
                    })

            pi_doc.insert(ignore_permissions=True)
            pi_doc.submit()

            frappe.msgprint(f"Purchase Invoice {pi_doc.name} created successfully")
            self.db_set("purchase_invoice", pi_doc.name)

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

        for item in self.petty_cash_items:
            if hasattr(item, "_vat_amount") and item._vat_amount > 0:
                if not self.vat_account:
                    self.vat_account = frappe.get_value("Company", self.company, "default_vat_account")

                gl_entries.append(self.get_gl_dict({
                    "account": self.vat_account,
                    "debit": flt(item._vat_amount),
                    "debit_in_account_currency": flt(item._vat_amount),
                    "against": self.account_paid_from,
                    "remarks": f"VAT for item {item.item_code}"
                }))

        total_debits = sum(flt(d.get("debit", 0)) for d in gl_entries)

        against_accounts = set()
        against_accounts.update(
            row.expense_account for row in self.petty_cash_details if row.expense_account
        )
        if hasattr(self, "petty_cash_items"):
            for item in self.petty_cash_items:
                if hasattr(item, "_vat_amount") and item._vat_amount > 0:
                    against_accounts.add(self.vat_account)

        gl_entries.append(self.get_gl_dict({
            "account": self.account_paid_from,
            "credit": flt(self.amount),
            "credit_in_account_currency": flt(self.amount),
            "against": ", ".join(against_accounts),
            "remarks": "Paid from Petty Cash Account"
        }))

        total_credits = sum(flt(d.get("credit", 0)) for d in gl_entries)

        frappe.msgprint(f"GL Entry Balancing:\n- Total Debits: {total_debits}\n- Total Credits: {total_credits}")

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
            "remarks": args.get("remarks") or f"Petty Cash Voucher: {self.name}",
            "account_currency": account_currency,
            "voucher_type": self.doctype,
            "voucher_no": self.name,
            "reference_type": self.doctype,
            "reference_name": self.name,
            "posting_time": nowdate(),
            "is_opening": "No"
        })
