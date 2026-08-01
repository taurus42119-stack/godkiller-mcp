# AGENTS.catalog — cold lists (ปากสั้น)

อ่านเมื่อ**ติดตั้ง / คัด** skill หรือ MCP — ไม่อ่านทุกเทิร์น.  
กฎจริงอยู่ที่ `AGENTS.md`. North star: proof + law + catalog — ของร้านนอก = อะไหล่ ไม่ใช่ระบบใหม่.

---

## Skill shops — กติคัดเข้า

1. ขาดช่องว่างจริง  
2. มี `name` + `description` ใน frontmatter  
3. สแกนความปลอดภัยก่อน (แนว SkillSpector)  
4. เข้า catalog แล้วโหลดทีละ ≤4  
5. ห้ามซ้ำของที่มีแล้ว  

| Repo | คำแนะนำ |
|---|---|
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | คุ้ม — anti-slop UI |
| [mattpocock/skills](https://github.com/mattpocock/skills) | คัดทีละอัน |
| [anthropics/skills](https://github.com/anthropics/skills) | อ้างรูปแบบ — อย่า duplicate ทั้งก้อน |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | มีแล้ว — ห้ามซ้ำ |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | เครื่องมือติดตั้ง ไม่ใช่เนื้อ |
| [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) | แนว catalog — เรามี `skill_catalog` แล้ว |
| [yusufkaraaslan/Skill_Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) | ทีหลัง |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | ทีหลัง |
| [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector) | เครื่องมือตรวจก่อนรับของแปลก |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | ย่อเข้า law — ไม่ต้อง 50 skills |
| [anbeime/skill](https://github.com/anbeime/skill) / ร้านรวม | อย่าดูดทั้งร้าน |
| pinchbench / skill-icons / colleague-skill / … | ข้าม — ไม่ช่วย claim gate |

### Bundled (selected)

| Path | Role |
|---|---|
| `design-taste-frontend` | anti-slop UI |
| `game-ready-3d-pipeline` | mesh pipeline |
| `game-development` | game bar |
| `threejs-runtime-craft` | Three/WebGL + local mirror + devtools |
| Vendor trees (addyosmani-skills, …) | craft packs; catalog dedupe |

---

## MCP shops — กติคัดเข้า

1. ขาดช่องว่างจริง  
2. ไม่ซ้ำหน้าที่ GODKILLER (อย่าเอา claim/done ซ้ำ)  
3. โยง evidence ได้  
4. เปิดตามโปรเจกต์ — ไม่ติดทั้ง awesome-list  

[awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) / [Awesome-MCP-ZH](https://github.com/yzfly/Awesome-MCP-ZH) = ร้าน — GODKILLER ไม่กลืน.

| MCP / repo | คำแนะนำ |
|---|---|
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | คุ้ม — UI F12 console+network ลำดับ 1 |
| [DmitriyGolub/threejs-devtools-mcp](https://github.com/DmitriyGolub/threejs-devtools-mcp) | มี — scene/material/light; พิจารณาตามงาน 3D |
| [@modelcontextprotocol/server-threejs](https://www.npmjs.com/package/@modelcontextprotocol/server-threejs) | มีทางเลือก — preview/docs |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | ทางเลือก E2E — อย่าซ้อนคู่ DevTools ถาวร |
| [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) | เมื่อ DCC 3D |
| [github/github-mcp-server](https://github.com/github/github-mcp-server) | คุ้ม — PR/issues |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | คุ้ม — AST/graph |
| [BrowserMCP/mcp](https://github.com/BrowserMCP/mcp) | ทางเลือกถ้ายังไม่มี browser MCP |
| [supabase/mcp](https://github.com/supabase/mcp) | เมื่อใช้ Supabase |
| AWS / Google / Oracle / Salesforce MCP | เมื่อ cloud นั้นเป็นงานจริง |
| [MicrosoftDocs/mcp](https://github.com/MicrosoftDocs/mcp) | เมื่อ Azure/MS docs |
| microsoft/mcp · mcp-for-beginners | เรียน/อ้าง — ไม่ติดตั้งทั้งก้อน |
| [activepieces/activepieces](https://github.com/activepieces/activepieces) | ทีหลัง — อย่าแทน GODKILLER |
| xiaohongshu / xiaozhi-esp32 | เฉพาะโดเมน |
| awesome ทั้งก้อน / Elastic เป็น MCP | ข้าม — search ใช้ IDE + GODKILLER gate พอ |
