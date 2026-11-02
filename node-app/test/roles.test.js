import {test} from 'node:test';
import assert from 'node:assert/strict';
import {can} from '../src/policies.js';
import {accountAction} from '../src/administration.js';
import {database} from '../src/database.js';
import {config} from '../src/config.js';
import {migrate} from '../src/schema.js';

const staff=(role,scope='STATE')=>({active:1,scopes:[{role,scope,active:1,...(scope==='DISTRICT'?{district_code:'A',district_active:1,state_active:1}:{})}]});
test('four application roles enforce permission and jurisdiction boundaries',()=>{
  assert(can(staff('ADMIN'),'accounts.manage'));
  assert(!can(staff('ADMIN','DISTRICT'),'accounts.manage'));
  assert(can(staff('MANAGER','DISTRICT'),'applications.approve',{district_code:'A'}));
  assert(!can(staff('MANAGER','DISTRICT'),'applications.approve',{district_code:'B'}));
  for(const cap of ['accounts.manage','system.change','applications.delete','organization.change','audit.view']) assert(!can(staff('MANAGER'),cap));
  assert(can(staff('EDITOR'),'news.review'));
  for(const cap of ['applications.view','applications.review','applications.approve','contacts.view','cards.issue','reports.export','trainings.manage']) assert(!can(staff('EDITOR'),cap));
  assert(can(staff('USER'),'facilitators.view'));
  for(const cap of ['news.view','news.review','applications.view','cards.issue','accounts.manage','trainings.manage']) assert(!can(staff('USER'),cap));
  assert(!can({...staff('ADMIN'),facilitator_id:'personal'},'accounts.manage'));
});
test('new role assignments persist and Admin must use state scope',async()=>{
  const db=await database({...config({}),sqlite:':memory:'});
  try {
    await migrate(db);
    await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',['root','root','root@example.invalid','unused']);
    await db.run('INSERT INTO gmf_users(id,username,email,password_hash) VALUES (?,?,?,?)',['staff','staff','staff@example.invalid','unused']);
    let revision=1;
    for(const role of ['USER','EDITOR','MANAGER','ADMIN']) await accountAction(db,'root',{action:'assign',user_id:'staff',revision:revision++,role,scope:'STATE',reason:'Role assignment test'});
    assert.equal((await db.all('SELECT id FROM gmf_scopes WHERE user_id=?',['staff'])).length,4);
    await assert.rejects(accountAction(db,'root',{action:'assign',user_id:'staff',revision,role:'ADMIN',scope:'DISTRICT',district:'A',reason:'Invalid scope'}),/matching/);
  } finally {await db.close();}
});
