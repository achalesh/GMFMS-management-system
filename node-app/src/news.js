import {randomUUID} from 'node:crypto';
import {loadUser,can,scopesFor} from './policies.js';
import {FormError} from './registration-fields.js';
import {ownFacilitator} from './facilitator-accounts.js';
import {authorization} from './cards.js';
import {policyLock} from './registration-services.js';
import {processNewsMedia} from './news-media.js';
export const newsStatuses={DRAFT:'Draft / കരട്',SUBMITTED:'Submitted / സമർപ്പിച്ചു',APPROVED:'Approved / അംഗീകരിച്ചു',CHANGES_REQUESTED:'Changes requested / തിരുത്തൽ ആവശ്യപ്പെട്ടു',REJECTED:'Rejected / നിരസിച്ചു'};
export const newsEditable=new Set(['DRAFT','CHANGES_REQUESTED']);
export const newsStaff=user=>!!user?.active&&!user.facilitator_id&&(!!user.superuser||scopesFor(user,'news.view').length>0);
export const newsSelect=`SELECT n.*,p.name AS panchayat_name,b.name AS block_name,d.name AS district_name,b.code AS block_code,d.code AS district_code FROM gmf_news n JOIN gmf_panchayats p ON p.code=n.panchayat_code JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code`;
export const newsSelectFor=db=>db.dialect==='mysql'?newsSelect.replace('p.code=n.panchayat_code','CAST(p.code AS BINARY)=CAST(n.panchayat_code AS BINARY)'):newsSelect;
export async function newsAuthor(db,userId){const profile=await ownFacilitator(db,userId);if(await authorization(db,profile.f)!=='ACTIVE')throw new FormError('Only active approved facilitators can submit news. / സജീവമായ അംഗീകൃത ഫെസിലിറ്റേറ്റർമാർക്ക് വാർത്ത സമർപ്പിക്കാം.',403);return profile;}
export async function newsRecord(db,user,id){const article=(await db.all(newsSelectFor(db)+' WHERE n.id=?',[id]))[0];if(!article||!user?.active||user.must_change||(user.facilitator_id?article.facilitator_id!==user.facilitator_id:article.status==='DRAFT'||!can(user,'news.view',article)))throw new FormError('News unavailable.',404);return {...article,tags:JSON.parse(article.hashtags)};}
export async function newsMedia(db,id){return db.all('SELECT id,kind,mime,size,position FROM gmf_news_media WHERE news_id=? ORDER BY position,id',[id]);}
export function newsValues(input,submit){
 const field=(key,max)=>{const value=input[key]??'';if(typeof value!=='string'||value.trim().length>max)throw new FormError('Check the '+key.replaceAll('_',' ')+'.');return value.trim();};
 const heading=field('heading',200),content=field('content',20000),programme_date=field('programme_date',10),rawTags=field('hashtags',2000),language=input.language||'ML';
 if(!['ML','EN','BOTH'].includes(language))throw new FormError('Choose Malayalam, English or both.');
 if(programme_date&&(!/^\d{4}-\d{2}-\d{2}$/.test(programme_date)||Number.isNaN(+new Date(programme_date))||new Date(programme_date).toISOString().slice(0,10)!==programme_date))throw new FormError('Enter a valid programme date. / പരിപാടിയുടെ ശരിയായ തീയതി നൽകുക.');
 if(submit&&(heading.length<3||content.length<20||!programme_date))throw new FormError('Add a heading (3–200 characters), news content (at least 20 characters) and programme date. / തലക്കെട്ടും വാർത്തയുടെ ഉള്ളടക്കവും പരിപാടിയുടെ തീയതിയും നൽകുക.');
 const tags=[];for(const raw of rawTags?rawTags.split(/[\s,]+/u):[]){const tag=raw.replace(/^#/,'').normalize('NFC');if(!/^(?=.*[\p{L}\p{N}])[\p{L}\p{M}\p{N}_\u200c\u200d]{1,60}$/u.test(tag))throw new FormError('Use hashtags with letters, numbers or underscores, separated by spaces. / ഹാഷ്‌ടാഗുകൾ സ്പേസ് ഉപയോഗിച്ച് വേർതിരിക്കുക.');const value='#'+tag;if(!tags.some(existing=>existing.toLowerCase()===value.toLowerCase()))tags.push(value);}if(tags.length>20)throw new FormError('Use at most 20 hashtags.');
 return {heading,content,programme_date,language,tags};
}
async function event(tx,id,userId,action,before,after,note){await tx.run('INSERT INTO gmf_news_events(id,news_id,actor_id,action,from_status,to_status,note,created_at) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),id,userId,action,before,after,note,Date.now()]);await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),userId,'news.'+action,Date.now()]);}
export async function saveNews(db,userId,id,input,files=[]){
 await newsAuthor(db,userId);if(!['draft','submit'].includes(input.action))throw new FormError('Choose Save draft or Submit news.');const value=newsValues(input,input.action==='submit');
 if(files.length>4)throw new FormError('Attach up to three images and one video.');const processed=[];for(const file of files)processed.push(await processNewsMedia(file));
 return db.transaction(async tx=>{
 await policyLock(tx);const {user,f}=await newsAuthor(tx,userId);let existing=null;
 const creationId=input.creation_id||randomUUID();if(!id&&(typeof creationId!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(creationId)))throw new FormError('Reload the new story form.');
 if(!id&&(await tx.all('SELECT id FROM gmf_news WHERE id=?',[creationId])).length){await newsRecord(tx,user,creationId);return creationId;}
 if(id){existing=await newsRecord(tx,user,id);if(!newsEditable.has(existing.status)||Number(input.revision)!==existing.revision)throw new FormError('News changed or is being reviewed. Reload before editing.',409);}
 const media=existing?await newsMedia(tx,id):[],remove=input.remove_media===undefined?[]:typeof input.remove_media==='string'?[input.remove_media]:input.remove_media;
 if(!Array.isArray(remove)||remove.length>4||remove.some(key=>!media.some(m=>m.id===key)))throw new FormError('Choose only your attached media to remove.');
 const retained=media.filter(m=>!remove.includes(m.id)),combined=[...retained,...processed];if(combined.filter(m=>m.kind==='IMAGE').length>3||combined.filter(m=>m.kind==='VIDEO').length>1)throw new FormError('Keep up to three images and one video. Remove an existing attachment before replacing it.');
 if(input.action==='draft'&&!value.heading&&!value.content&&!combined.length)throw new FormError('Add a heading, news content or media before saving a draft.');
 const articleId=id||creationId,now=Date.now(),status=input.action==='submit'?'SUBMITTED':'DRAFT';
 if(existing)await tx.run('UPDATE gmf_news SET author_name=?,panchayat_code=?,heading=?,content=?,hashtags=?,programme_date=?,language=?,status=?,revision=revision+1,updated_at=?,submitted_at=? WHERE id=?',[f.full_name,f.panchayat_code,value.heading,value.content,JSON.stringify(value.tags),value.programme_date,value.language,status,now,status==='SUBMITTED'?now:null,articleId]);
 else await tx.run('INSERT INTO gmf_news(id,number,facilitator_id,author_name,panchayat_code,heading,content,hashtags,programme_date,language,status,created_at,updated_at,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[articleId,'NEWS-'+new Date().getUTCFullYear()+'-'+articleId.replaceAll('-','').slice(0,16).toUpperCase(),f.id,f.full_name,f.panchayat_code,value.heading,value.content,JSON.stringify(value.tags),value.programme_date,value.language,status,now,now,status==='SUBMITTED'?now:null]);
 for(const key of remove)await tx.run('DELETE FROM gmf_news_media WHERE id=? AND news_id=?',[key,articleId]);
 let position=Math.max(0,...retained.map(m=>m.position))+1;for(const file of processed)await tx.run('INSERT INTO gmf_news_media(id,news_id,kind,mime,size,sha256,body,position) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),articleId,file.kind,file.mime,file.body.length,file.sha256,file.body,position++]);
 await event(tx,articleId,userId,input.action==='submit'?'submitted':'draft_saved',existing?.status||'',status,'Facilitator saved news.');return articleId;
 });
}
export async function reviewNews(db,userId,id,input){return db.transaction(async tx=>{await policyLock(tx);const user=await loadUser(tx,userId),article=await newsRecord(tx,user,id);if(!can(user,'news.review',article))throw new FormError('News review access denied.',403);
 if(article.revision!==Number(input.revision)||!['SUBMITTED','APPROVED'].includes(article.status))throw new FormError('News changed. Reload before reviewing.',409);
 const transitions={approve:'APPROVED',changes:'CHANGES_REQUESTED',reject:'REJECTED'};const target=typeof input.action==='string'&&Object.hasOwn(transitions,input.action)?transitions[input.action]:null;if(!target||article.status==='APPROVED'&&input.action!=='changes')throw new FormError('Choose a valid editorial action.');const reason=typeof input.reason==='string'?input.reason.trim():'';if(!reason||reason.length>2000)throw new FormError('Provide editorial feedback within 2,000 characters.');
 await tx.run('UPDATE gmf_news SET status=?,revision=revision+1,updated_at=? WHERE id=?',[target,Date.now(),id]);await event(tx,id,userId,'review_'+input.action,article.status,target,reason);
 });}
