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
                    company: frm.doc.company
                }   
            };
        });
    },

    validate: function(frm) {
        calculate_totals(frm);

        const total_combined = flt(frm.doc.total) + flt(frm.doc.total_vat);
        if (flt(frm.doc.amount) !== total_combined) {
            frappe.throw(`The total of Petty Cash Details (${frm.doc.total}) and VAT Details (${frm.doc.total_vat}) must equal the Amount (${frm.doc.amount}).`);
        }
    }
});

frappe.ui.form.on('Petty Cash Details', {
    debit: function(frm) {
        calculate_totals(frm);
    },
    petty_cash_details_add: function(frm,cdt,cdn) {
        calculate_totals(frm);

        const row = locals[cdt][cdn];
        if (frm.doc.company) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Company",
                    filters: { name: frm.doc.company },
                    fieldname: "cost_center"
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, "cost_center", r.message.cost_center);
                    }
                }
            });
        }
    },
    petty_cash_details_remove: function(frm) {
        calculate_totals(frm);
    },
    cost_center: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.cost_center && frm.doc.company) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Company",
                    filters: { name: frm.doc.company },
                    fieldname: "cost_center"
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, "cost_center", r.message.cost_center);
                    }
                }
            });
        }
    },
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
}
