import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {assessSnapshot} from '../src/migration-assessment.js';
const digest=body=>createHash('sha256').update(body).digest('hex');
function sample(){const file=Buffer.from('synthetic artifact');const data={format:'gramaswaraj-django-snapshot-v1',records:[{model:'idcards.identitycard',pk:'synthetic',fields:{}}],files:{synthetic:{size:file.length,body:file.toString('base64'),sha256:digest(file)}}};const bytes=Buffer.from(JSON.stringify(data));return {data,bytes,manifest:{snapshot_sha256:digest(bytes),counts:{'idcards.identitycard':1},artifact_count:1}};}
test('migration assessment refuses tampering and incomplete reconciliation',()=>{
 const {bytes,manifest}=sample();assert.throws(()=>assessSnapshot(Buffer.concat([bytes,Buffer.from(' ')]),manifest));assert.throws(()=>assessSnapshot(bytes,{...manifest,counts:{'idcards.identitycard':2}}));assert.throws(()=>assessSnapshot(bytes,{...manifest,artifact_count:0}));
});
test('migration assessment preserves card blocker and checks artifacts independently',()=>{
 const {data,bytes,manifest}=sample(),result=assessSnapshot(bytes,manifest);assert.equal(result.operational_import_ready,false);assert.equal(result.target_modified,false);assert.match(result.blockers[0],/cards/);
 data.files.synthetic.body=Buffer.from('tampered artifact').toString('base64');const bad=Buffer.from(JSON.stringify(data));assert.throws(()=>assessSnapshot(bad,{...manifest,snapshot_sha256:digest(bad)}));
});
