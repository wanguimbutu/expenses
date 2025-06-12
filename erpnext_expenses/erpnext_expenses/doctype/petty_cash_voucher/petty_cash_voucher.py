import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.accounts.utils import get_account_currency

class PettyCashVoucher(Document):
    def validate(self):
       # self.validate_user_account_access()
        self.calculate_totals()
        self.set_default_cost_centers()


    def calculate_totals(self):
        for row in self.petty_cash_items:
            row.amount = flt(row.qty) * flt(row.rate)
        self.total = sum(flt(row.debit) for row in self.petty_cash_details)
        self.total_vat = sum(flt(row.amount) for row in self.vat_details)
        self.items_total = sum(flt(row.amount) for row in self.petty_cash_items)
        self.amount = self.total + self.total_vat + self.items_total


    def set_default_cost_centers(self):
        default_cc = frappe.db.get_value("Company", self.company, "cost_center")
        for row in self.petty_cash_details:
                if not row.cost_center:
                    row.cost_center = default_cc

    def on_submit(self):
        self.make_gl_entries(cancel=False)
        self.update_inventory()

    def on_cancel(self):
        self.make_gl_entries(cancel=True)

    def make_gl_entries(self, cancel=False):
        gl_entries = []

        # Debit: Petty Cash Details
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

        # Debit: VAT Details
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

        # Credit: Account Paid From
        gl_entries.append(self.get_gl_dict({
            "account": self.account_paid_from,
            "credit": flt(self.amount),
            "credit_in_account_currency": flt(self.amount),
            "against": ", ".join(
                [row.expense_account for row in self.petty_cash_details if row.expense_account]
            ),
            "remarks": "Paid from Petty Cash Account"
        }))

        # Submit GL Entries
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
    
    def update_inventory(self):
        for row in self.petty_cash_items:
            if not row.item_code or not row.warehouse:
                frappe.throw("Each item must have an Item Code and Warehouse.")

            # Create stock ledger entry
            frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": self.company,
                "items": [{
                    "item_code": row.item_code,
                    "qty": row.qty,
                    "t_warehouse": row.warehouse,
                    "rate": row.rate
                }]
            }).insert(ignore_permissions=True).submit()
