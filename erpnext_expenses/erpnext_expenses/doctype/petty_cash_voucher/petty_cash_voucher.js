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

        // Updated validation to include items_total
        const total_combined = flt(frm.doc.total) + flt(frm.doc.total_vat) + flt(frm.doc.items_total);
        if (flt(frm.doc.amount) !== total_combined) {
            frappe.throw(`The total of Petty Cash Details (${frm.doc.total}), VAT Details (${frm.doc.total_vat}), and Items Total (${frm.doc.items_total}) must equal the Amount (${frm.doc.amount}).`);
        }
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

// New: Handle Petty Cash Items table calculations
frappe.ui.form.on('Petty Cash Items', {
    qty: function(frm, cdt, cdn) {
        calculate_item_amount(frm, cdt, cdn);
    },
    
    rate: function(frm, cdt, cdn) {
        calculate_item_amount(frm, cdt, cdn);
    },
    
    amount: function(frm) {
        calculate_totals(frm);
    },
    
    petty_cash_items_add: function(frm) {
        calculate_totals(frm);
    },
    
    petty_cash_items_remove: function(frm) {
        calculate_totals(frm);
    }
});

// Function to calculate individual item amount (rate * qty)
function calculate_item_amount(frm, cdt, cdn) {
    const item = locals[cdt][cdn];
    const amount = flt(item.rate || 0) * flt(item.qty || 0);
    
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    
    // Refresh the field to show updated value
    frm.refresh_field('petty_cash_items');
    
    // Calculate totals after updating amount
    calculate_totals(frm);
}

// Updated calculate_totals function to include petty cash items
function calculate_totals(frm) {
    let total = 0;
    let total_vat = 0;
    let items_total = 0;

    // Calculate Petty Cash Details total
    if (frm.doc.petty_cash_details) {
        frm.doc.petty_cash_details.forEach(row => {
            total += flt(row.debit);
        });
    }

    // Calculate VAT Details total
    if (frm.doc.vat_details) {
        frm.doc.vat_details.forEach(row => {
            total_vat += flt(row.amount);
        });
    }

    // Calculate Petty Cash Items total
    if (frm.doc.petty_cash_items) {
        frm.doc.petty_cash_items.forEach(row => {
            items_total += flt(row.amount);
        });
    }

    // Set individual totals
    frm.set_value('total', total);
    frm.set_value('total_vat', total_vat);
    frm.set_value('items_total', items_total);

    // Calculate and set grand total (amount field)
    const grand_total = total + total_vat + items_total;
    frm.set_value('amount', grand_total);
}