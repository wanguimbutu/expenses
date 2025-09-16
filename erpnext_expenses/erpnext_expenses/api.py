import frappe
import json

@frappe.whitelist()
def unreconcile_payment_entries(from_date, to_date, customer=None):
    from_date = from_date
    to_date = to_date
    
    
    filters = {
        "posting_date": ["between", [from_date, to_date]], 
        "docstatus": 1
    }
    
    if customer:
        filters["party"] = customer
    
    payment_entries = frappe.get_all(
        "Payment Entry",
        filters=filters,
        fields=["name", "company", "party", "party_name"]
    )
    
    results = []
    for pe in payment_entries:
        try:
            payment_doc = frappe.get_doc("Payment Entry", pe.name)
            if not payment_doc.references:
                continue

            selection_map = []
            for ref in payment_doc.references:
                if ref.allocated_amount and ref.allocated_amount > 0:
                    selection_map.append({
                        "company": pe.company,
                        "voucher_type": "Payment Entry",
                        "voucher_no": pe.name,
                        "against_voucher_type": ref.reference_doctype,
                        "against_voucher_no": ref.reference_name
                    })

            if not selection_map:
                continue

            result = frappe.get_attr(
                "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.create_unreconcile_doc_for_selection"
            )(selections=json.dumps(selection_map))
            
            frappe.db.commit()
            results.append({ "payment_entry": pe.name, "status": "success", "result": result })
        except Exception as e:
            frappe.db.rollback()
            results.append({ "payment_entry": pe.name, "status": "failed", "error": str(e) })
    
    return results
