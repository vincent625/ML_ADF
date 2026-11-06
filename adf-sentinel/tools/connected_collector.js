// Run inside a Codex functions.exec session, where the approved `tools` object exists.
// No credentials are accepted or copied. All upstream operations are read-only.
// Change batchLimit to resume another bounded batch; remaining work is never discarded.
const workspace = "/rhome/yanzhu/ML_ADF";
const project = workspace + "/adf-sentinel";
const site = "https://lsg-thermofisher.atlassian.net";
const batchLimit = 100;
const allowed = new Set(["getConfluenceContent", "getConfluenceContentDescendants", "listConfluenceContentVersions", "getConfluenceContentVersion", "listConfluenceAttachments", "listConfluenceComments", "resolveConfluenceContentMacros", "getJiraIssue", "listJiraIssueComments", "listJiraIssueChangelogs", "listJiraIssueRemoteIssueLinks", "searchJiraIssuesUsingJql"]);
async function saved(path, value) {
  const content = JSON.stringify(value, null, 2);
  await tools.apply_patch("*** Begin Patch\n*** Add File: " + project + "/" + path + "\n+" + content.split("\n").join("\n+") + "\n*** End Patch");
}
async function localJson(path) {
  let r = await tools.exec_command({cmd:project+"/.venv/bin/python "+project+"/tools/select_requests.py --limit "+batchLimit, workdir:workspace, login:false, max_output_tokens:60000, yield_time_ms:1000});
  let out = r.output;
  while (r.session_id) {r = await tools.write_stdin({session_id:r.session_id, chars:"", yield_time_ms:1000, max_output_tokens:120000}); out += r.output;}
  if (r.exit_code !== 0) throw new Error("Work queue not readable");
  return JSON.parse(out);
}
function unpack(r) {for (const c of r.content || []) if(c.type === "text") {try {const d=JSON.parse(c.text); return d.data || d;} catch {}} return r.structuredContent || r;}
const queue = (await localJson("data/collection_queue.json")).slice(0, batchLimit);
let done = 0;
await Promise.all(Array.from({length:4}, async () => {
  for (;;) {
    const j = queue.shift(); if (!j) return;
    if (!allowed.has(j.operation)) throw new Error("Operation is outside read-only registry");
    let inputs = j.inputs, page = 0;
    for (;;) {
      let response;
      for (let attempt=0; attempt<4; attempt++) {
        if (j.operation === "getJiraIssue") response = await tools.mcp__atlassian__getJiraIssue({cloudId:site,...inputs});
        else if (j.operation === "getConfluenceContent") response = await tools.mcp__atlassian__getConfluenceContent({cloudId:site,...inputs});
        else if (j.operation === "listJiraIssueComments") response = await tools.mcp__atlassian__listJiraIssueComments({cloudId:site,...inputs});
        else if (j.operation === "searchJiraIssuesUsingJql") response = await tools.mcp__atlassian__searchJiraIssuesUsingJql({cloudId:site,...inputs});
        else response = await tools.mcp__atlassian__executeRead({cloudId:site,name:j.operation,inputs,view:j.operation==="listJiraIssueChangelogs"?"evidence":undefined});
        const d = unpack(response), code = d.statusCode;
        if (![429,500,502,503,504].includes(code) || attempt === 3) break;
        await new Promise(resolve=>setTimeout(resolve, Math.min(30000, Number(d.retryAfter || 2**attempt)*1000)));
      }
      const d = unpack(response), confluence = j.operation.includes("Confluence");
      const prefix = {getConfluenceContent:"page",getConfluenceContentVersion:"version_body",listConfluenceAttachments:"attachments",listConfluenceContentVersions:"versions",listConfluenceComments:"comments",getConfluenceContentDescendants:"descendants",resolveConfluenceContentMacros:"macros",getJiraIssue:"issue",listJiraIssueComments:"comments",listJiraIssueChangelogs:"changelog",listJiraIssueRemoteIssueLinks:"remote"}[j.operation] || "batch";
      const resource = j.resource.replaceAll(":", "_").replace(/^page_/, "");
      await saved("data/raw/connected/"+(confluence?"confluence/":"jira/")+prefix+"_"+resource+"_"+(inputs.startAt || inputs.versionNumber || page)+"_"+j.id+".json",{tool:j.operation,job:j,resource:j.resource,request:inputs,collected_at:new Date().toISOString(),response});
      if (response.isError || d.error) break;
      let next = null;
      if (["listJiraIssueComments","listJiraIssueChangelogs"].includes(j.operation)) {
        const rows = d.comments || d.values || d.histories || [], end=(d.startAt || inputs.startAt || 0)+rows.length;
        if (d.isLast===false || (d.total!=null && end<d.total)) {if(!rows.length)throw new Error("Pagination stalled for "+j.resource); next={...inputs,startAt:end};}
      } else if (d.nextPageToken) next={...inputs,nextPageToken:d.nextPageToken};
      else {let cursor=d.nextCursor; const link=d._links?.next; if(link&&!cursor)cursor=new URL(link,site).searchParams.get("cursor"); if(cursor) {if(cursor===inputs.cursor)throw new Error("Repeated cursor");next={...inputs,cursor};}}
      if (!next) break;
      inputs=next;page++;
    }
    done++;if(done%20===0)notify({completed:done,batchLimit,remainingQueue:"preserved on disk"});
  }
}));
text({completed:done,next:"Run ingest to reconcile the new responses, then resume this runner."});
