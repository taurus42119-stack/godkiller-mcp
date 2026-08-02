# GODKILLER — copy-paste prompts

Use these in the IDE chat. Do not invent a longer ritual.

---

## New project (first time in this folder)

```text
โปรเจกต์นี้ยังไม่ติด GODKILLER
รัน: python -m godkiller_mcp.bootstrap --workspace .
อย่า commit godkiller-write-guard.local.cmd
เสร็จแล้วบอกให้ฉัน Reload Antigravity
ยังไม่เขียนโค้ดแอป
```

After reload (optional — only if you want Write lock proven):

```text
พิสูจน์ write-guard: deny ไฟล์นอก allowlist, allow หลัง set_paths
ยังไม่เขียนฟีเจอร์
```

---

## Start work (every feature)

```text
/plan
ทำ: <อธิบายสิ่งที่ต้องการ>
หลังแผนผ่าน ค่อย /ultradeep Phase 1
ก่อนแก้ไฟล์ให้ gk_guard.set_paths ตามไฟล์ใน Phase
จบด้วย /verify แล้ว claim_done — ห้ามบอก done จากแชทอย่างเดียว
```

---

## Hook broken / Python moved

```text
รัน python -m godkiller_mcp.bootstrap --workspace . อีกครั้ง
อย่า commit godkiller-write-guard.local.cmd
เสร็จแล้วบอกให้ Reload
ยังไม่เขียนโค้ดแอป
```

---

## Cheat sheet

| When | Prompt block |
| --- | --- |
| New folder | **New project** above |
| Normal coding | **Start work** above |
| Write not blocked | **Hook broken** above |
