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

    // Don't calculate totals in frontend anymore
    validate: function(frm) {
        // Do nothing - backend will handle all totals
    }
});

frappe.ui.form.on('Petty Cash Details', {
    petty_cash_details_add: function(frm, cdt, cdn) {
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

// No amount calculations for Petty Cash Items or VAT in frontend anymore
