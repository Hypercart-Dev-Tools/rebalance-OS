![rebalance](https://github.com/user-attachments/assets/c77f8362-bd1d-4447-b68d-c3b1bb408d9b)# rebalance OS 

> Your workday OS

**Status: Coming soon — active development. Star to follow along.**

---

## Who this is for

- **Dev and design agency owners** juggling 5+ client repos, scattered notes, and back-to-back meetings with no time to connect the dots
- **Solopreneurs and indie hackers** who live in Obsidian but lose hours tracking where their attention actually goes
- **Technical founders** who want AI-assisted clarity on their own work — without sending their notes, commits, or calendar to a cloud service

If you've ever opened your laptop in the morning and genuinely not known where to start, this is for you.

---

## The problem

Your work lives in three places that never talk to each other: your notes, your code repos, and your calendar. You context-switch constantly, lose track of which projects are getting too much attention (and which aren't getting enough), and spend the first 30 minutes of every day reconstructing what you were doing yesterday.

AI assistants could help — but they can't see your Obsidian vault, your GitHub activity, or your Google Calendar. And sending all of that to a cloud LLM isn't an option for client work.

![Uploa<svg width="100%" viewBox="0 0 680 580" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </marker>
  <mask id="imagine-text-gaps-ucee2s" maskUnits="userSpaceOnUse"><rect x="0" y="0" width="680" height="580" fill="white"/><rect x="36" y="15.078125" width="75.890625" height="17.765625" fill="black" rx="2"/><rect x="44.359375" y="51.234375" width="115.28125" height="21.53125" fill="black" rx="2"/><rect x="65.109375" y="70.484375" width="73.78125" height="19.03125" fill="black" rx="2"/><rect x="216.46875" y="51.234375" width="107.0625" height="21.53125" fill="black" rx="2"/><rect x="214.359375" y="70.484375" width="111.28125" height="19.03125" fill="black" rx="2"/><rect x="401.984375" y="51.234375" width="54.03125" height="21.53125" fill="black" rx="2"/><rect x="378.09375" y="70.484375" width="101.8125" height="19.03125" fill="black" rx="2"/><rect x="532.5625" y="51.234375" width="100.875" height="21.53125" fill="black" rx="2"/><rect x="538.484375" y="70.484375" width="89.03125" height="19.03125" fill="black" rx="2"/><rect x="36" y="129.078125" width="193.96875" height="17.765625" fill="black" rx="2"/><rect x="129.375" y="161.234375" width="87.25" height="21.515625" fill="black" rx="2"/><rect x="77.734375" y="178.484375" width="190.53125" height="19.03125" fill="black" rx="2"/><rect x="423.640625" y="161.234375" width="142.71875" height="21.515625" fill="black" rx="2"/><rect x="401.921875" y="178.484375" width="186.15625" height="19.03125" fill="black" rx="2"/><rect x="36" y="235.078125" width="164.9375" height="17.765625" fill="black" rx="2"/><rect x="189" y="277.25" width="302" height="21.515625" fill="black" rx="2"/><rect x="155.625" y="298.484375" width="368.75" height="19.015625" fill="black" rx="2"/><rect x="155.625" y="318.484375" width="368.75" height="19.015625" fill="black" rx="2"/><rect x="36" y="389.078125" width="91.078125" height="17.765625" fill="black" rx="2"/><rect x="67.1875" y="425.25" width="109.625" height="21.515625" fill="black" rx="2"/><rect x="59.875" y="444.484375" width="124.25" height="19.015625" fill="black" rx="2"/><rect x="273.90625" y="425.25" width="112.1875" height="21.515625" fill="black" rx="2"/><rect x="285.828125" y="444.484375" width="88.34375" height="19.015625" fill="black" rx="2"/><rect x="485.546875" y="425.25" width="124.90625" height="21.515625" fill="black" rx="2"/><rect x="491.9375" y="444.484375" width="112.125" height="19.015625" fill="black" rx="2"/><rect x="80.75" y="502.5" width="518.5" height="19" fill="black" rx="2"/><rect x="72.234375" y="520.5" width="535.53125" height="19" fill="black" rx="2"/></mask></defs>

  <!-- ── LLM CLIENTS (top tier) ── -->
  <text x="40" y="28" style="fill:var(--color-text-tertiary);font-size:11px;letter-spacing:0.07em;fill:rgb(115, 114, 108);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:8.8px;font-weight:400;text-anchor:start;dominant-baseline:auto">LLM clients</text>

  <g onclick="sendPrompt('How does Claude Desktop connect to MCP?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="28" y="40" width="148" height="52" rx="8" stroke-width="0.5" style="fill:rgb(238, 237, 254);stroke:rgb(83, 74, 183);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="102" y="62" text-anchor="middle" dominant-baseline="central" style="fill:rgb(60, 52, 137);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">Claude Desktop</text>
    <text x="102" y="80" text-anchor="middle" dominant-baseline="central" style="fill:rgb(83, 74, 183);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">MCP native</text>
  </g>

  <g onclick="sendPrompt('How does VS Code Agent Mode use MCP tools?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="196" y="40" width="148" height="52" rx="8" stroke-width="0.5" style="fill:rgb(238, 237, 254);stroke:rgb(83, 74, 183);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="270" y="62" text-anchor="middle" dominant-baseline="central" style="fill:rgb(60, 52, 137);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">VS Code agent</text>
    <text x="270" y="80" text-anchor="middle" dominant-baseline="central" style="fill:rgb(83, 74, 183);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">Copilot / Continue</text>
  </g>

  <g onclick="sendPrompt('How does Cursor use MCP servers?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="364" y="40" width="130" height="52" rx="8" stroke-width="0.5" style="fill:rgb(238, 237, 254);stroke:rgb(83, 74, 183);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="429" y="62" text-anchor="middle" dominant-baseline="central" style="fill:rgb(60, 52, 137);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">Cursor</text>
    <text x="429" y="80" text-anchor="middle" dominant-baseline="central" style="fill:rgb(83, 74, 183);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">MCP compatible</text>
  </g>

  <g onclick="sendPrompt('What other MCP-compatible clients exist?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="514" y="40" width="138" height="52" rx="8" stroke-width="0.5" stroke-dasharray="5 3" style="fill:rgb(241, 239, 232);stroke:rgb(95, 94, 90);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-dasharray:4px, 2.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="583" y="62" text-anchor="middle" dominant-baseline="central" style="fill:rgb(68, 68, 65);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">Future clients</text>
    <text x="583" y="80" text-anchor="middle" dominant-baseline="central" style="fill:rgb(95, 94, 90);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">Any MCP host</text>
  </g>

  <!-- Arrows from clients down to transport -->
  <line x1="102" y1="92" x2="102" y2="148" marker-end="url(#arrow)" mask="url(#imagine-text-gaps-ucee2s)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="270" y1="92" x2="270" y2="148" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="429" y1="92" x2="380" y2="148" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="583" y1="92" x2="490" y2="148" marker-end="url(#arrow)" stroke-dasharray="5 3" opacity="0.5" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-dasharray:4px, 2.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:0.5;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>

  <!-- ── TRANSPORT LAYER ── -->
  <text x="40" y="142" style="fill:var(--color-text-tertiary);font-size:11px;letter-spacing:0.07em;fill:rgb(115, 114, 108);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:8.8px;font-weight:400;text-anchor:start;dominant-baseline:auto">Transport (standard MCP spec)</text>

  <g onclick="sendPrompt('What is the MCP JSON-RPC transport protocol?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="28" y="154" width="290" height="44" rx="8" stroke-width="0.5" style="fill:rgb(225, 245, 238);stroke:rgb(15, 110, 86);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="173" y="172" text-anchor="middle" dominant-baseline="central" style="fill:rgb(8, 80, 65);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">stdio (local)</text>
    <text x="173" y="188" text-anchor="middle" dominant-baseline="central" style="fill:rgb(15, 110, 86);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">JSON-RPC 2.0 over stdin/stdout</text>
  </g>

  <g onclick="sendPrompt('When should I use SSE transport vs stdio?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="338" y="154" width="314" height="44" rx="8" stroke-width="0.5" style="fill:rgb(225, 245, 238);stroke:rgb(15, 110, 86);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="495" y="172" text-anchor="middle" dominant-baseline="central" style="fill:rgb(8, 80, 65);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">SSE / HTTP (remote)</text>
    <text x="495" y="188" text-anchor="middle" dominant-baseline="central" style="fill:rgb(15, 110, 86);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">For network-accessible servers</text>
  </g>

  <!-- Arrows transport to server -->
  <line x1="173" y1="198" x2="280" y2="254" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="495" y1="198" x2="390" y2="254" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>

  <!-- ── MCP SERVER (core) ── -->
  <text x="40" y="248" style="fill:var(--color-text-tertiary);font-size:11px;letter-spacing:0.07em;fill:rgb(115, 114, 108);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:8.8px;font-weight:400;text-anchor:start;dominant-baseline:auto">MCP server (obsidian_rag)</text>

  <g onclick="sendPrompt('What tools should the MCP server expose?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="28" y="260" width="624" height="100" rx="12" stroke-width="0.5" style="fill:rgb(250, 236, 231);stroke:rgb(153, 60, 29);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="340" y="288" text-anchor="middle" dominant-baseline="central" style="fill:rgb(113, 43, 19);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">obsidian-rag MCP server (Python, mcp SDK)</text>
    <text x="340" y="308" text-anchor="middle" dominant-baseline="central" style="fill:rgb(153, 60, 29);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">Tools: query_notes  github_balance  todays_agenda  search_vault</text>
    <text x="340" y="328" text-anchor="middle" dominant-baseline="central" style="fill:rgb(153, 60, 29);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">No LLM-specific logic — pure tool definitions + JSON responses</text>
  </g>

  <!-- Arrows server to adapters -->
  <line x1="175" y1="360" x2="130" y2="408" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="340" y1="360" x2="340" y2="408" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <line x1="505" y1="360" x2="550" y2="408" marker-end="url(#arrow)" style="fill:none;stroke:rgb(115, 114, 108);color:rgb(0, 0, 0);stroke-width:1.2px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>

  <!-- ── ADAPTERS ── -->
  <text x="40" y="402" style="fill:var(--color-text-tertiary);font-size:11px;letter-spacing:0.07em;fill:rgb(115, 114, 108);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:8.8px;font-weight:400;text-anchor:start;dominant-baseline:auto">Data adapters</text>

  <g onclick="sendPrompt('How does the SQLite adapter work?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="28" y="414" width="188" height="52" rx="8" stroke-width="0.5" style="fill:rgb(250, 238, 218);stroke:rgb(133, 79, 11);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="122" y="436" text-anchor="middle" dominant-baseline="central" style="fill:rgb(99, 56, 6);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">SQLite adapter</text>
    <text x="122" y="454" text-anchor="middle" dominant-baseline="central" style="fill:rgb(133, 79, 11);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">chunks, embeddings</text>
  </g>

  <g onclick="sendPrompt('How does the GitHub adapter scan repos?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="236" y="414" width="188" height="52" rx="8" stroke-width="0.5" style="fill:rgb(250, 238, 218);stroke:rgb(133, 79, 11);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="330" y="436" text-anchor="middle" dominant-baseline="central" style="fill:rgb(99, 56, 6);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">GitHub adapter</text>
    <text x="330" y="454" text-anchor="middle" dominant-baseline="central" style="fill:rgb(133, 79, 11);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">PAT, REST API</text>
  </g>

  <g onclick="sendPrompt('How does the calendar adapter call gcalcli?')" style="fill:rgb(0, 0, 0);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto">
    <rect x="444" y="414" width="208" height="52" rx="8" stroke-width="0.5" style="fill:rgb(250, 238, 218);stroke:rgb(133, 79, 11);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
    <text x="548" y="436" text-anchor="middle" dominant-baseline="central" style="fill:rgb(99, 56, 6);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:11.2px;font-weight:500;text-anchor:middle;dominant-baseline:central">Calendar adapter</text>
    <text x="548" y="454" text-anchor="middle" dominant-baseline="central" style="fill:rgb(133, 79, 11);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">gcalcli subprocess</text>
  </g>

  <!-- ── KEY RULE callout ── -->
  <rect x="28" y="494" width="624" height="44" rx="8" stroke-width="0.5" style="fill:var(--color-background-secondary);stroke:var(--color-border-secondary);fill:rgb(245, 244, 237);stroke:rgba(31, 30, 29, 0.3);color:rgb(0, 0, 0);stroke-width:0.4px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:16px;font-weight:400;text-anchor:start;dominant-baseline:auto"/>
  <text x="340" y="512" text-anchor="middle" dominant-baseline="central" style="fill:var(--color-text-secondary);fill:rgb(61, 61, 58);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">Design rule: server returns plain JSON only — no Claude-specific markup, no XML tool tags</text>
  <text x="340" y="530" text-anchor="middle" dominant-baseline="central" style="fill:var(--color-text-secondary);fill:rgb(61, 61, 58);stroke:none;color:rgb(0, 0, 0);stroke-width:0.8px;stroke-linecap:butt;stroke-linejoin:miter;opacity:1;font-family:&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif;font-size:9.6px;font-weight:400;text-anchor:middle;dominant-baseline:central">Each LLM client wraps results in its own format — the server never knows which LLM called it</text>

</svg>ding rebalance.svg…]()


---

## What it does

**obsidian-rag** is a local-first morning briefing engine that ingests your Obsidian vault, GitHub activity, and calendar into a queryable SQLite database — then lets any MCP-compatible LLM (Claude, Copilot, Cursor, Continue) answer questions about your own work, flag over-investment in specific projects, and surface what actually needs your attention today.

---

## Use cases

**Morning briefing**
Ask "What's my day look like?" and get today's meetings, yesterday's commit activity, and a summary of relevant notes — in one shot, from your local machine.

**Project balance check**
"Am I over-investing in client X?" surfaces commit velocity, PR activity, and note density per project. Flags when one repo is consuming >40% of your attention.

**Knowledge retrieval**
"What did I decide about the LTVera embedding pipeline?" Semantic search across your entire vault, ranked by relevance, answered by a local LLM.

**Handoff prep**
"Summarize everything I know about Project Y" pulls notes, recent commits, and open issues into a coherent brief — useful for client updates, team handoffs, or just getting back up to speed after a break.

**Coming soon: Slack activity** (via Sleuth bolt app integration) — adds team communication context to the balance picture.

---

## High-level architecture

```
Data sources
  Google Calendar  ──┐
  GitHub activity  ──┤──▶  cron (daily)  ──▶  SQLite + sqlite-vec
  Obsidian vault   ──┤         │                (chunks, embeddings,
  Slack [soon]     ──┘         │                 github_activity)
                               │
                               ▼
                     MCP server (Python)
                     obsidian-rag tools:
                       query_notes
                       github_balance
                       todays_agenda
                       search_vault
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       Claude Desktop     VS Code agent      Cursor
       (MCP native)    (Copilot/Continue)  (MCP compatible)
```

The MCP server speaks standard JSON-RPC — no LLM-specific logic inside it. Any MCP-compatible client works without modification.

---

## Why Markdown files and local LLMs make this possible

Obsidian stores everything as plain `.md` files. No proprietary database, no sync lock-in, no API needed — just a folder on your disk. That makes ingestion a simple recursive file scan: parse frontmatter, chunk by headings, extract tags and wikilinks, embed, and index. The entire vault becomes a queryable vector store in a single SQLite file.

Local LLMs — specifically Qwen3 via Ollama — close the loop. Your notes, commits, and calendar events never leave your machine. There's no API key to manage for inference, no usage bill, and no terms-of-service risk with client data. The model runs on-device (optimized for Apple Silicon via MLX), retrieves context from the local vector store, and answers in seconds.

The result is an AI assistant that actually knows your work — because it's reading the same files you are.

---

## Tech stack

| Layer | Tool |
|---|---|
| Notes | Obsidian (plain `.md`) |
| Vector DB | SQLite + `sqlite-vec` |
| Embeddings | Qwen3-Embedding via Ollama |
| LLM | Qwen3-7B via Ollama (Apple Silicon optimized) |
| Calendar | `gcalcli` → Google Calendar API |
| GitHub | GitHub REST API + PAT |
| MCP server | Python `mcp` SDK (stdio + SSE) |
| LLM clients | Claude Desktop, VS Code, Cursor, any MCP host |

---

## Roadmap

- [x] Architecture and design
- [ ] Obsidian ingester (`ingest.py`)
- [ ] SQLite schema + sqlite-vec setup
- [ ] Qwen3 embedding pipeline
- [ ] GitHub activity scanner
- [ ] gcalcli calendar adapter
- [ ] MCP server with core tools
- [ ] Morning briefing CLI
- [ ] Slack integration via Sleuth bolt app

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**.

You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice.

See [LICENSE](./LICENSE) for the full license text, or visit https://www.apache.org/licenses/LICENSE-2.0.

---

## Contributing

Not open to contributions yet — getting the core right first. Watch the repo and come back when the first milestone lands.

---

*Built by [Hypercart](https://hypercart.com) — tools for agencies and solopreneurs who build on WordPress.*
