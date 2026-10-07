import {FormError} from './registration-fields.js';
export async function uniqueContacts(db,personal,exclude=''){
 const mobile=personal.mobile,email=(personal.email||'').trim().toLowerCase();
 const rows=await db.all("SELECT mobile,email FROM gmf_applications WHERE id<>? AND (mobile=? OR (?<>'' AND LOWER(email)=?))",[exclude,mobile,email,email]);
 if(rows.some(r=>r.mobile===mobile))throw new FormError('This mobile number is already registered. Use a different number or contact the administrator.');
 if(email&&rows.some(r=>r.email.toLowerCase()===email))throw new FormError('This email address is already registered. Use a different email or contact the administrator.');
}
export async function panchayatCapacity(db,panchayat,exclude=''){
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});
 const [row]=await db.all("SELECT COUNT(*) AS n FROM gmf_facilitators f LEFT JOIN gmf_registry_meta m ON m.id=f.id WHERE f.panchayat_code=? AND f.id<>? AND f.status IN ('ACTIVE','SUSPENDED','INACTIVE') AND f.valid_until>=? AND COALESCE(m.ended,0)=0",[panchayat,exclude,today]);
 if(Number(row.n)>=3)throw new FormError('This panchayat already has three current members. End an existing membership before appointing or transferring another member.',409);
}
