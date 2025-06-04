frappe.ui.form.on('Petty Cash Voucher', {
    onload: function(frm) {

        if (!frm.doc.posting_date) {
            frm.set_value('posting_date', frappe.datetime.get_today());
        }

        if (!frm.doc.company && frappe.defaults.get_default("company")) {
            frm.set_value('company', frappe.defaults.get_default("company"));
        }

        frm.set_query("account_paid_from", () => {
            return {
                filters: {
                    root_type: ["in", ["Asset"]],
                    account_type: ["in", ["Cash", "Bank"]],
                    company: frm.doc.company,
                    user: frappe.session.user
                }
            };
        });
    },

    validate: function(frm) {
        calculate_totals(frm);
    }
});

frappe.ui.form.on('Petty Cash Details', {
    debit: function(frm) {
        calculate_totals(frm);
    },
    petty_cash_details_add: function(frm) {
        calculate_totals(frm);
    },
    petty_cash_details_remove: function(frm) {
        calculate_totals(frm);
    }
});

frappe.ui.form.on('Petty Cash Vat Details', {
    amount: function(frm) {
        calculate_totals(frm);
    },
    vat_account: function(frm) {
        calculate_totals(frm);
    },
    vat_details_add: function(frm) {
        calculate_totals(frm);
    },
    vat_details_remove: function(frm) {
        calculate_totals(frm);
    }
});

function calculate_totals(frm) {
    let total = 0;
    let total_vat = 0;

    frm.doc.petty_cash_details.forEach(row => {
        total += flt(row.debit);
    });

    frm.doc.vat_details.forEach(row => {
        total_vat += flt(row.amount);
    });

    frm.set_value('total', total);
    frm.set_value('total_vat', total_vat);
    frm.set_value('amount', total + total_vat);
}
