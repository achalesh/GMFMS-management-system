import {readFileSync} from 'node:fs';
export const catalog=JSON.parse(readFileSync(new URL('../data/registration-catalog.json',import.meta.url),'utf8'));
export class FormError extends Error{constructor(message,status=400){super(message);this.status=status;}}
const field=(name,label,max=150,required=false,type='text')=>({name,label,max,required,type});
export const fields={
 2:[field('full_name','Full name',150,true),field('name_ml','Name in Malayalam',180),{...field('gender','Gender'),options:['','female','male','other']},field('date_of_birth','Date of birth',10,false,'date'),field('mobile','Mobile number',20,true,'tel'),field('whatsapp','WhatsApp number (leave blank to use mobile)',20,false,'tel'),field('email','Email',254,false,'email'),field('address','Residential address',1500,true,'textarea'),field('pin_code','PIN code',6,true),field('emergency_name','Emergency contact name'),field('emergency_relationship','Emergency relationship',80),field('emergency_mobile','Emergency mobile',20,false,'tel')],
 3:[field('occupation','Occupation'),field('qualification','Educational qualification',180),field('current_organization','Current organization',180),field('designation','Designation'),field('media_experience','Media experience',2000,false,'textarea'),field('years_experience','Years of media experience',2,true,'number'),{...field('skills','Skills'),options:catalog.SKILLS,multiple:true},field('other_skill','Other skill',200),{...field('languages','Languages',150,true),options:catalog.LANGUAGES,multiple:true},field('other_language','Other language',100)],
 4:[{...field('equipment','Equipment you can access'),options:catalog.EQUIPMENT,multiple:true},field('other_equipment','Other equipment',200),...['facebook','instagram','youtube','twitter','linkedin','other_profile'].map(k=>field(k,k.replace('_',' '),250,false,'url'))]
};
export const titles=['Location','Personal details','Professional details','Equipment and profiles','Photograph and documents','Review and consent'];
export const slots=['photo',...catalog.DOCUMENTS.map(([code])=>'doc_'+code)];
export function mobile(value){const v=value.replace(/[\s()-]/g,'').replace(/^\+91/,'');if(!/^[6-9][0-9]{9}$/.test(v))throw new FormError('Enter a valid 10-digit Indian mobile number.');return v;}
export async function validateStep(db,step,input){
 const output={};
 if(step===1){
 for(const k of ['district','block','panchayat']){if(typeof input[k]!=='string'||input[k].length>30)throw new FormError('Choose a valid location.');output[k]=input[k];}
 const rows=await db.all(`SELECT p.code FROM gmf_panchayats p JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code JOIN gmf_states s ON s.code=d.state_code WHERE p.code=? AND b.code=? AND d.code=? AND p.active=1 AND b.active=1 AND d.active=1 AND s.active=1`,[output.panchayat,output.block,output.district]);
 if(!rows.length)throw new FormError('Choose an active panchayat within the selected block and district.');return output;
 }
 if(!fields[step])throw new FormError('Unknown registration step.');
 for(const f of fields[step]){
 if(f.multiple){const value=input[f.name]===undefined?[]:Array.isArray(input[f.name])?input[f.name]:[input[f.name]];if(value.length>f.options.length||value.some(v=>!f.options.includes(v))||(f.required&&!value.length))throw new FormError('Choose valid '+f.label.toLowerCase()+'.');output[f.name]=[...new Set(value)];}
 else{const value=input[f.name]??'';if(typeof value!=='string'||value.trim().length>f.max||(f.required&&!value.trim()))throw new FormError('Check '+f.label.toLowerCase()+'.');output[f.name]=value.trim();if(f.options&&!f.options.includes(output[f.name]))throw new FormError('Choose a valid '+f.label.toLowerCase()+'.');if(f.type==='url'&&value){try{const url=new URL(value);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw Error();}catch{throw new FormError('Use an HTTP or HTTPS profile URL without login credentials.');}}}
 }
 if(step===2){
 output.mobile=mobile(output.mobile);output.whatsapp=output.whatsapp?mobile(output.whatsapp):output.mobile;
 if(output.emergency_mobile)output.emergency_mobile=mobile(output.emergency_mobile);
 if(!/^[1-9][0-9]{5}$/.test(output.pin_code))throw new FormError('Enter a six-digit Indian PIN code.');
 if(output.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(output.email))throw new FormError('Enter a valid email.');output.email=output.email.toLowerCase();
 const emergency=[output.emergency_name,output.emergency_relationship,output.emergency_mobile];if(emergency.some(Boolean)&&!emergency.every(Boolean))throw new FormError('Complete all emergency contact fields or leave all blank.');
 if(output.date_of_birth){const value=output.date_of_birth,date=new Date(value),now=new Date();if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||Number.isNaN(+date)||date.toISOString().slice(0,10)!==value||date>now||date.getUTCFullYear()<now.getUTCFullYear()-120)throw new FormError('Enter a valid date of birth in the past.');}
 }
 if(step===3){if(!/^\d{1,2}$/.test(output.years_experience)||Number(output.years_experience)>80)throw new FormError('Years of experience must be between 0 and 80.');}
 for(const [key,other] of [['skills','other_skill'],['languages','other_language'],['equipment','other_equipment']])if(output[key]?.includes('Other')&&!output[other])throw new FormError('Please specify your other '+key+'.');
 return output;
}
