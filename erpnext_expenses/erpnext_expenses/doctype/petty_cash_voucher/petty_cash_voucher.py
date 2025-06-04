import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.accounts.utils import get_account_currency


class PettyCashVoucher(Document):
    def validate(self):
        self.total = sum(flt(row.debit) for row in self.petty_cash_details)
        self.calculate_totals()

    def validate_user_account_access(self):
        allowed_accounts = frappe.get_all("User Permission",
            filters={"user": frappe.session.user, "allow": "Account"},
            pluck="for_value"
        )
        if self.account_paid_from and self.account_paid_from not in allowed_accounts:
            frappe.throw(frappe._("You are not permitted to use account {0}").format(self.account_paid_from))
	
    def calculate_totals(self):
        self.total = sum(flt(row.debit) for row in self.petty_cash_details)
        self.total_vat = sum(flt(row.amount) for row in self.vat_details)
        self.amount = self.total + self.total_vat
    
    def on_submit(self):
        self.make_gl_entries(cancel=False)

    def on_cancel(self):
        self.make_gl_entries(cancel=True)

    def make_gl_entries(self, cancel=False):
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
                "project":row.project
            }, row=row))
            

        for vat in self.vat_details:
            if not vat.vat_account:
                frappe.throw("VAT Account is required in VAT Details.")
            gl_entries.append(self.get_gl_dict({
                "account": vat.vat_account,
                "credit": flt(vat.amount),
                "credit_in_account_currency": flt(vat.amount),
                "against": self.account_paid_from,
                "remarks": "VAT Entry"
            }))

        total_vat_amount = sum(flt(v.amount) for v in self.vat_details)

        gl_entries.append(self.get_gl_dict({
            "account": self.account_paid_from,
            "credit": flt(self.total) - total_vat_amount,
            "credit_in_account_currency": flt(self.total) - total_vat_amount,
            "against": ", ".join(
                [row.expense_account for row in self.petty_cash_details if row.expense_account]
            ),
            "remarks": "Net payment"
        }))


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
            "remarks": args.get("remarks") or self.remarks or "Petty Cash Voucher",
            "account_currency": account_currency,
            "voucher_type": self.doctype,
            "voucher_no": self.name,
            "posting_time": nowdate(),
            "is_opening": "No"
        })