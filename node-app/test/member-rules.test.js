import {test} from 'node:test';
import assert from 'node:assert/strict';
import {uniqueContacts} from '../src/member-rules.js';
test('MySQL contact matching uses binary comparisons and skips the blank-email comparison',async()=>{
 const queries=[];const db={dialect:'mysql',all:async(sql,args)=>{queries.push({sql,args});return [];}};
 await uniqueContacts(db,{mobile:'9876543210',email:'USER@example.invalid'},'own-id');
 assert.match(queries[0].sql,/CAST\(LOWER\(email\) AS BINARY\)=CAST\(\? AS BINARY\)/);
 assert.deepEqual(queries[0].args,['own-id','9876543210','user@example.invalid']);
 await uniqueContacts(db,{mobile:'9876543210',email:''});
 assert.doesNotMatch(queries[1].sql,/LOWER\(email\)|\?<>''/);
 assert.deepEqual(queries[1].args,['','9876543210']);
 db.all=async()=>[{mobile:'9999999999',email:'USER@example.invalid'}];
 await assert.rejects(uniqueContacts(db,{mobile:'9876543210',email:'user@example.invalid'}),/email address is already registered/);
});
