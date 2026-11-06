# Read-only access and collection contracts

The live run used the approved Atlassian MCP reader. No passwords/API tokens were requested in chat, found in saved HTML, or forwarded to another host. GitHub reads used its approved connector and immutable commit/blob IDs. Source-system operations were read-only.

Primary API documentation inspected for the optional REST implementation:

- [Confluence v2 descendants](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-descendants/): cursor/depth traversal; follow the returned next link.
- [Confluence v2 pages](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/): current page body and metadata, independent of release chronology.
- [Confluence versions](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-version/): historical version metadata; the connected reader supplies historical bodies.
- [Confluence attachments](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-attachment/): inventories and separate authorized downloads.
- [Jira issues and changelogs](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/): all available fields and separately paginated changelog.
- [Jira comments](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/): counts, actual page sizes and continuation.
- [Jira search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/): enhanced JQL search with next-page tokens.
- [Jira remote links](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-remote-links/): external links are distinct from formal issue-to-issue links.

The connected reader's historical-body, descendant, attachment, macro, changelog and remote-link operations were discovered before invocation. Jira `getIssue` embedded changelog is not used as a complete history: it cannot be correctly paginated. Comments retrieved via issue fields are reconciled against reported totals, and additional pages are read when needed. A pagination stall or repeated cursor is a partial failure, never completion.

The project accepts genuine native JSON exports and its own archived response envelope (`tool`, `request`, `collected_at`, `response`). Collector checkpoints and stable request IDs preserve multiple release associations while avoiding association-driven refetching. Probe/refresh snapshots remain separate raw evidence and are deduplicated by issue key for model preparation.

Confluence `children` and `toc` macro wrappers can be unsupported by macro rendering. The actual seed descendants were retrieved through the native descendant operation; the missing visual macro is not interpreted as an empty child tree. Unsupported macro states remain in raw/extracted manifests.

The REST fallback uses an explicit site allowlist, approved environment credentials, GET-only routes, bounded retries, Retry-After handling, a four-worker pool and durable pagination work. Operations not mapped to a verified endpoint remain pending for the connected reader. It refuses redirects carrying authorization. Attachment downloads use a separate credential-free, approved HTTPS-storage allowlist and never reuse Jira credentials.

No Xray, JFrog or internal Genexus-run authentication is invented. References are preserved for an approved reader/export. A saved uncovered Xray panel does not override narrative evidence that testing happened elsewhere; it identifies a traceability gap.
