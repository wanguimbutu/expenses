frappe.ui.form.on('Petty Cash Voucher', {
    refresh: function(frm) {
        frm.events.calculate_total(frm);
    },
    onload: function (frm) {
        if (!frm.doc.posting_date) {
            frm.set_value('posting_date', frappe.datetime.get_today());
        }

        if (!frm.doc.company) {
            frappe.call({
                method: "frappe.defaults.get_user_default",
                args: {
                    "key": "company"
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value("company", r.message);
                    }
                }
            });
        }
        frm.set_query('account_paid_from', () => {
            return {
                query: 'erpnext.controllers.queries.get_cash_or_bank_account',
                filters: {
                    company: frm.doc.company,
                    user: frappe.session.user
                }
            };
        });
    },
    petty_cash_details_on_form_rendered: function(frm, cdt, cdn) {
        frappe.model.on(cdt, cdn, 'debit', function() {
            frm.events.calculate_total(frm);
        });
    },
    petty_cash_details_add: function(frm) {
        frm.events.calculate_total(frm);
    },
    petty_cash_details_remove: function(frm) {
        frm.events.calculate_total(frm);
    },
    calculate_total: function(frm) {
        let total = 0;
        frm.doc.petty_cash_details.forEach(row => {
            total += flt(row.debit);
        });
        frm.set_value('total', total);
    }
});