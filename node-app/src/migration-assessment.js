import {createHash} from 'node:crypto';
const hash=body=>createHash('sha256').update(body).digest('hex');
export function assessSnapshot(bytes,manifest){
 if(hash(bytes)!==manifest.snapshot_sha256)throw Error('Snapshot integrity mismatch');
 const snapshot=JSON.parse(bytes.toString('utf8'));
 if(snapshot.format!=='gramaswaraj-django-snapshot-v1'||!Array.isArray(snapshot.records)||!snapshot.files)throw Error('Unsupported snapshot format');
 const counts={},keys=new Set();
 for(const row of snapshot.records){
  if(typeof row.model!=='string'||!row.fields||row.pk===undefined)throw Error('Invalid source record');
  const key=row.model+':'+row.pk;if(keys.has(key))throw Error('Duplicate source identity');keys.add(key);
  counts[row.model]=(counts[row.model]||0)+1;
 }
 for(const model of new Set([...Object.keys(counts),...Object.keys(manifest.counts)]))if((counts[model]||0)!==manifest.counts[model])throw Error('Source count mismatch');
 if(Object.keys(snapshot.files).length!==manifest.artifact_count)throw Error('Artifact count mismatch');
 for(const file of Object.values(snapshot.files)){
  if(typeof file.body!=='string'||typeof file.sha256!=='string')throw Error('Invalid source artifact');
  const body=Buffer.from(file.body,'base64');
  if(body.length!==file.size||hash(body)!==file.sha256)throw Error('Artifact integrity mismatch');
 }
 const blockers=[];
 if(counts['idcards.identitycard'])blockers.push('Issued Django cards use different token formats and source digests. Preserve card URLs/PDFs and verify compatibility before switching domains.');
 if(counts['facilitators.facilitatorappointment'])blockers.push('Django appointment ledger includes dates, status and approval history beyond the Node registry snapshots. Map and reconcile the ledger before import.');
 if(counts['registrations.correctionrequest'])blockers.push('Correction ticket formats differ. Existing applicant links require an explicit compatibility or replacement plan.');
 if(counts['registrations.registrationdraft'])blockers.push('Drafts are tied to Django browser sessions. Preserve submitted records separately; unsubmitted drafts need a reviewed expiry or continuation policy.');
 const records=snapshot.records;
 if(records.some(r=>r.model==='organization.systemsetting'&&(r.fields.max_upload_mb!==5||r.fields.one_primary_per_panchayat!==true||r.fields.public_directory_enabled)))blockers.push('Source system policy differs from supported Node upload/primary/public-directory behavior. Resolve policy parity before import.');
 if(records.some(r=>r.model==='accounts.user'&&r.fields.is_active&&!/^pbkdf2_sha256\$/.test(r.fields.password)&&!r.fields.password.startsWith('!')))blockers.push('An active account uses a password format not supported by Node. Plan credential migration without resetting passwords silently.');
 return {snapshot_verified:true,source_modified:false,target_modified:false,counts:manifest.counts,artifact_count:manifest.artifact_count,operational_import_ready:false,blockers,next_step:'Create a dedicated Hostinger staging MySQL database; resolve mapping blockers before an operational import.'};
}
