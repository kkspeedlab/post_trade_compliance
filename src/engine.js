/* Pure RM-204 trade-reconciliation engine. No file or network access. */
export const STATUSES=Object.freeze({FULL:"Fully Executed",PARTIAL:"Partially Executed",NONE:"Not Executed"});
function str(v){return String(v??"").trim().toUpperCase()}
function qty(v){const n=Number(v);if(!Number.isFinite(n)||n<0)throw new Error("Invalid nonnegative quantity: "+v);return n}
function date(v){const s=String(v??"").trim();if(/^\d{8}$/.test(s))return s;if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s.replaceAll("-","");throw new Error("Invalid ISO or YYYYMMDD date: "+v)}
export function reconcile(orders,executions,asOf){
 const cutoff=date(asOf),results=[],issues=[],used=new Set();
 const eligible=executions.map((e,i)=>({...e,_i:i,account:str(e.account),bank:str(e.bank),isin:str(e.isin),side:str(e.side),tradeDate:date(e.tradeDate),quantity:qty(e.quantity)}))
   .filter(e=>e.tradeDate<=cutoff);
 for(const [idx,raw] of orders.entries()){
  const o={...raw,account:str(raw.account),bank:str(raw.bank),isin:str(raw.isin),side:str(raw.side),quantity:qty(raw.quantity),orderDate:date(raw.orderDate)};
  if(!o.account||!o.bank||!o.isin||!["BUY","SELL"].includes(o.side))throw new Error("Invalid order fields at index "+idx);
  const candidates=eligible.filter(e=>!used.has(e._i)&&e.account===o.account&&e.bank===o.bank&&e.isin===o.isin&&e.side===o.side&&e.tradeDate>=o.orderDate);
  const siblings=orders.filter((x,j)=>j!==idx&&str(x.account)===o.account&&str(x.bank)===o.bank&&str(x.isin)===o.isin&&str(x.side)===o.side&&date(x.orderDate)<=cutoff);
  // Without a shared bank order ID, do not arbitrarily allocate fills between overlapping same-security orders.
  const ambiguous=siblings.length>0&&candidates.length>0;
  if(ambiguous){issues.push({orderIndex:idx,code:"AMBIGUOUS_MATCH",message:"Multiple orders share account, bank, ISIN and side. Manual attribution required."});results.push({...o,executed:0,outstanding:o.quantity,status:STATUSES.NONE,executionRefs:[],review:"Ambiguous match"});continue}
  let remaining=o.quantity,applied=0;const refs=[];
  for(const e of candidates.sort((a,b)=>a.tradeDate.localeCompare(b.tradeDate)||a._i-b._i)){
    if(remaining<=0)break;
    const take=Math.min(remaining,e.quantity);
    if(take<e.quantity){issues.push({orderIndex:idx,code:"SPLIT_FILL",message:"Execution quantity exceeds remaining order quantity; manual attribution required."});continue}
    used.add(e._i);remaining-=take;applied+=take;refs.push({reference:e.reference||"",quantity:take,tradeDate:e.tradeDate,settlementDate:e.settlementDate||null,price:e.price??null});
  }
  results.push({...o,executed:applied,outstanding:remaining,status:remaining===0?STATUSES.FULL:applied>0?STATUSES.PARTIAL:STATUSES.NONE,executionRefs:refs,review:""});
 }
 return {asOf:cutoff,orders:results,issues,unmatchedExecutions:eligible.filter(e=>!used.has(e._i)).map(e=>({reference:e.reference||"",account:e.account,bank:e.bank,isin:e.isin,tradeDate:e.tradeDate,quantity:e.quantity}))};
}
