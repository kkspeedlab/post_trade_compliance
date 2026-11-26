import test from "node:test";
import assert from "node:assert/strict";
import {reconcile,STATUSES} from "../src/engine.js";
const order={account:"ADV",bank:"UBS",isin:"FR0000120271",side:"BUY",quantity:699,orderDate:"20261117"};
test("fully executed across multiple bank executions",()=>{
 const r=reconcile([order],[{account:"ADV",bank:"UBS",isin:order.isin,side:"BUY",quantity:400,tradeDate:"20261117",reference:"A"},{account:"ADV",bank:"UBS",isin:order.isin,side:"BUY",quantity:299,tradeDate:"20261118",reference:"B"}],"20261119");
 assert.equal(r.orders[0].status,STATUSES.FULL);assert.equal(r.orders[0].outstanding,0);
});
test("partial and as-of cutoff",()=>{
 const r=reconcile([order],[{account:"ADV",bank:"UBS",isin:order.isin,side:"BUY",quantity:400,tradeDate:"20261117",reference:"A"},{account:"ADV",bank:"UBS",isin:order.isin,side:"BUY",quantity:299,tradeDate:"20261120",reference:"B"}],"20261119");
 assert.equal(r.orders[0].status,STATUSES.PARTIAL);assert.equal(r.orders[0].outstanding,299);
});
test("no execution",()=>assert.equal(reconcile([order],[],"20261119").orders[0].status,STATUSES.NONE));
test("ambiguous duplicate orders flagged",()=>{
 const r=reconcile([order,{...order,quantity:100}],[{account:"ADV",bank:"UBS",isin:order.isin,side:"BUY",quantity:699,tradeDate:"20261117"}],"20261119");
 assert.equal(r.issues.filter(x=>x.code==="AMBIGUOUS_MATCH").length,2);
});
