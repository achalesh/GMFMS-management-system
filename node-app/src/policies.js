const common=['dashboard.view','facilitators.view','locations.view'];
const review=['applications.view','applications.review','contacts.view'];
const manage=['applications.approve','facilitators.change','cards.issue','reports.export'];
export const capabilities={SUPER_ADMIN:[...common,...review,...manage,'organization.change','system.change','accounts.manage','audit.view','locations.manage','applications.delete'],STATE_ADMIN:[...common,...review,...manage,'organization.change','audit.view'],DISTRICT_ADMIN:[...common,...review,...manage],BLOCK_COORDINATOR:[...common,...review],REVIEWER:[...common,...review],ID_CARD_OPERATOR:[...common,'cards.issue'],VIEWER:common};
const globalOnly=new Set(['organization.change','system.change','accounts.manage','audit.view','locations.manage','applications.delete']);
export function scopesFor(user,capability){
 if(!user?.active)return [];
 return (user.scopes||[]).filter(s=>{
 if(!s.active||!capabilities[s.role]?.includes(capability))return false;
 if(['SUPER_ADMIN','STATE_ADMIN'].includes(s.role)&&s.scope!=='STATE')return false;
 if(s.role==='DISTRICT_ADMIN'&&s.scope!=='DISTRICT')return false;
 if(s.role==='BLOCK_COORDINATOR'&&s.scope!=='BLOCK')return false;
 if(s.scope==='STATE')return !s.district_code&&!s.block_code;
 if(!s.district_code||!s.district_active||!s.state_active)return false;
 if(s.scope==='DISTRICT')return !s.block_code;
 return s.scope==='BLOCK'&&s.block_code&&s.block_active&&s.block_district===s.district_code;
 });
}
export function can(user,capability,place){
 if(!user?.active||!Object.values(capabilities).some(v=>v.includes(capability)))return false;
 if(user.superuser)return true;
 return scopesFor(user,capability).some(s=>s.scope==='STATE'||(!globalOnly.has(capability)&&(place?s.district_code===place.district_code&&(s.scope==='DISTRICT'||s.block_code===place.block_code):['dashboard.view','locations.view'].includes(capability))));
}
export async function loadUser(db,id){
 const rows=await db.all('SELECT u.id,u.username,u.email,u.active,u.superuser,COALESCE(m.must_change,0) AS must_change FROM gmf_users u LEFT JOIN gmf_account_meta m ON m.id=u.id WHERE u.id=? AND u.active=1',[id]);
 if(!rows[0])return null;
 const scopes=await db.all(`SELECT j.*, d.active AS district_active, s.active AS state_active, b.active AS block_active, b.district_code AS block_district FROM gmf_scopes j LEFT JOIN gmf_districts d ON d.code=j.district_code LEFT JOIN gmf_states s ON s.code=d.state_code LEFT JOIN gmf_blocks b ON b.code=j.block_code WHERE j.user_id=?`,[id]);
 return {...rows[0],scopes};
}
