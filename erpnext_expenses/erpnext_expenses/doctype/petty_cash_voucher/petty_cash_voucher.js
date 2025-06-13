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
        toggle_child_tables(frm);
    },
    refresh: function(frm) {
        toggle_child_tables(frm);
    },

    is_expense: function(frm) {
        if (frm.doc.is_expense) {
            frm.set_value('is_purchase', 0);
        }
        toggle_child_tables(frm);
    },

    is_purchase: function(frm) {
        if (frm.doc.is_purchase) {
            frm.set_value('is_expense', 0);
        }
        toggle_child_tables(frm);
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

function calculate_item_amount(frm, cdt, cdn) {
    const item = locals[cdt][cdn];
    const amount = flt(item.rate || 0) * flt(item.qty || 0);
    
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    
    frm.refresh_field('petty_cash_items');
    
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0;
    let total_vat = 0;
    let items_total = 0;

    if (frm.doc.petty_cash_details) {
        frm.doc.petty_cash_details.forEach(row => {
            total += flt(row.debit);
        });
    }

    if (frm.doc.vat_details) {
        frm.doc.vat_details.forEach(row => {
            total_vat += flt(row.amount);
        });
    }

    if (frm.doc.petty_cash_items) {
        frm.doc.petty_cash_items.forEach(row => {
            items_total += flt(row.amount);
        });
    }

    frm.set_value('total', total);
    frm.set_value('total_vat', total_vat);
    frm.set_value('items_total', items_total);

    const grand_total = total + total_vat + items_total;
    frm.set_value('amount', grand_total);
}

function toggle_child_tables(frm) {
    const show_expense = frm.doc.is_expense === 1;
    const show_purchase = frm.doc.is_purchase === 1;

    frm.toggle_display('petty_cash_details', show_expense);
    frm.toggle_display('vat_details', show_expense);
    frm.toggle_display('total', show_expense);
    frm.toggle_display('total_vat', show_expense);

    frm.toggle_display('petty_cash_items', show_purchase);
    frm.toggle_display('items_total', show_purchase);
}
