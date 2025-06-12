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
    }
});

frappe.ui.form.on('Petty Cash Details', {
    debit: function(frm) {
        calculate_totals(frm);
    },
    petty_cash_details_add: function(frm, cdt, cdn) {
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

frappe.ui.form.on('Petty Cash Items', {
    qty: function(frm, cdt, cdn) {
        update_amount_and_totals(frm, cdt, cdn);
    },
    rate: function(frm, cdt, cdn) {
        update_amount_and_totals(frm, cdt, cdn);
    },
    petty_cash_items_add: function(frm) {
        calculate_totals(frm);
    },
    petty_cash_items_remove: function(frm) {
        calculate_totals(frm);
    }
});

function update_amount_and_totals(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const amount = flt(row.qty) * flt(row.rate);

    frappe.model.set_value(cdt, cdn, "amount", amount).then(() => {
        calculate_totals(frm);
    });
}

function calculate_totals(frm) {
    let total = 0;
    let total_vat = 0;
    let items_total = 0;

    frm.doc.petty_cash_details.forEach(row => {
        total += flt(row.debit);
    });

    frm.doc.vat_details.forEach(row => {
        total_vat += flt(row.amount);
    });

    frm.doc.petty_cash_items.forEach(row => {
        items_total += flt(row.qty) * flt(row.rate);
    });

    frm.set_value("total", total);
    frm.set_value("total_vat", total_vat);
    frm.set_value("items_total", items_total);

    frm.set_value("amount", flt(total) + flt(total_vat) + flt(items_total));
}
