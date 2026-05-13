"""Agent Platform — 科幻风格交互式 AI 助手。

启动:
    cd agent-platform
    PYTHONPATH="src;../single-agent/src;../mcp-server;../rag-system/src" streamlit run src/agent_platform/ui.py
"""

import streamlit as st
import asyncio, sys, os, re, json, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import bcrypt
from supabase import create_client

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "single-agent" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-server"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "rag-system" / "src"))

# ============================================================
st.set_page_config(page_title="Nexus AI", page_icon="", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# RAG 缓存目录
DATA_DIR = Path(__file__).parent.parent.parent / "data"
try:
    DATA_DIR.mkdir(exist_ok=True)
except PermissionError:
    import tempfile
    DATA_DIR = Path(tempfile.gettempdir()) / "agent-platform-data"
    DATA_DIR.mkdir(exist_ok=True)

# Supabase 数据库（替代 SQLite，云持久化）
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yjojlhlbokkihxlqowmg.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_xOAS8QKEqVDLHcqsh3aYvQ_yPFuAf3K")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def hpw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def check_pw(pw, h): return bcrypt.checkpw(pw.encode(), h.encode())
def sanitize(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")[:50]

def register_user(u, pw):
    try:
        existing = _supabase.table("users").select("id").eq("username", u.strip()).execute()
        if existing.data: return False, "用户名已存在"
        _supabase.table("users").insert({"username": u.strip(), "password_hash": hpw(pw)}).execute()
        return True, "注册成功"
    except Exception as e:
        return False, f"注册失败: {e}"

def login_user(u, pw):
    try:
        r = _supabase.table("users").select("id,password_hash").eq("username", u.strip()).execute()
        if not r.data: return False, "用户不存在", None
        row = r.data[0]
        if not check_pw(pw, row["password_hash"]): return False, "密码错误", None
        return True, "登录成功", row["id"]
    except Exception as e:
        return False, f"登录失败: {e}", None

def save_conv(uid, q, a, tools, tokens, srcs):
    try:
        _supabase.table("conversations").insert({
            "user_id": uid, "question": q, "answer": a[:3000],
            "tools_used": json.dumps(tools, ensure_ascii=False),
            "tokens": tokens, "sources": json.dumps(srcs, ensure_ascii=False),
        }).execute()
    except Exception:
        pass

def load_convs(uid, limit=20):
    try:
        r = _supabase.table("conversations").select("*").eq("user_id", uid).order("id", desc=True).limit(limit).execute()
        return list(reversed(r.data)) if r.data else []
    except Exception:
        return []

def del_conv(cid):
    try:
        _supabase.table("conversations").delete().eq("id", cid).execute()
    except Exception:
        pass

def clear_convs(uid):
    try:
        _supabase.table("conversations").delete().eq("user_id", uid).execute()
    except Exception:
        pass

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&display=swap');
.stApp::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse at 20% 50%,rgba(72,49,212,0.15)0%,transparent 50%),radial-gradient(ellipse at 80% 20%,rgba(0,210,255,0.1)0%,transparent 50%),radial-gradient(ellipse at 50% 80%,rgba(168,85,247,0.1)0%,transparent 50%),linear-gradient(135deg,#0a0a1a 0%,#0d1117 30%,#0a1628 60%,#0a0a1a 100%);z-index:-1;animation:bgPulse 8s ease-in-out infinite}
@keyframes bgPulse{0%,100%{opacity:1}50%{opacity:0.85}}
.stApp::after{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background-image:radial-gradient(1px 1px at 10% 30%,rgba(255,255,255,0.8),transparent),radial-gradient(1px 1px at 25% 70%,rgba(255,255,255,0.6),transparent),radial-gradient(1.5px 1.5px at 40% 10%,rgba(255,255,255,0.9),transparent),radial-gradient(1px 1px at 55% 60%,rgba(255,255,255,0.5),transparent),radial-gradient(1.5px 1.5px at 70% 40%,rgba(255,255,255,0.7),transparent),radial-gradient(1px 1px at 85% 80%,rgba(255,255,255,0.6),transparent),radial-gradient(1.5px 1.5px at 60% 20%,rgba(255,255,255,0.8),transparent),radial-gradient(1px 1px at 35% 50%,rgba(100,200,255,0.7),transparent),radial-gradient(1px 1px at 75% 15%,rgba(200,150,255,0.6),transparent),radial-gradient(1px 1px at 5% 45%,rgba(100,255,200,0.7),transparent);z-index:-1;animation:starTwinkle 3s ease-in-out infinite alternate}
@keyframes starTwinkle{0%{opacity:0.7}100%{opacity:1}}
.stApp,.stMarkdown,p,li,label,div{color:#e0e6ed!important}
h1,h2,h3{color:#fff!important;font-family:'Orbitron',monospace}
[data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(10,10,26,0.98)0%,rgba(13,17,35,0.95)40%,rgba(10,22,40,0.98)100%)!important;border-right:1px solid rgba(72,49,212,0.3)!important;box-shadow:4px 0 20px rgba(72,49,212,0.15)!important}
[data-testid="stSidebar"]::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#4831d4,#00d2ff,#4831d4,transparent);animation:scanLine 3s linear infinite}
@keyframes scanLine{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.user-bubble{background:linear-gradient(135deg,#4831d4 0%,#6c5ce7 100%);color:#fff;padding:14px 18px;border-radius:18px 18px 4px 18px;margin:10px 0;max-width:80%;margin-left:auto;box-shadow:0 4px 15px rgba(72,49,212,0.35);word-wrap:break-word}
.agent-bubble{border:1px solid rgba(72,49,212,0.2);border-radius:16px;padding:16px;margin:10px 0;background:rgba(20,25,40,0.6)}
.thought-card{background:rgba(255,152,0,0.12);border-left:3px solid #ff9800;padding:10px 14px;margin:4px 0 4px 20px;border-radius:4px 12px 12px 4px;font-size:0.9em;color:#ffe0b2}
.tool-card{background:rgba(0,200,83,0.12);border-left:3px solid #00c853;padding:10px 14px;margin:4px 0 4px 20px;border-radius:4px 12px 12px 4px;font-size:0.9em;color:#b9f6ca}
.source-card{background:rgba(0,176,255,0.12);border-left:3px solid #00b0ff;padding:8px 12px;margin:2px 0;border-radius:4px 8px 8px 4px;font-size:0.8em}
.stChatInput textarea{border-radius:24px!important;border:2px solid rgba(72,49,212,0.4)!important;background:rgba(15,18,30,0.9)!important;color:#e0e6ed!important}
.stChatInput textarea:focus{border-color:#00d2ff!important;box-shadow:0 0 20px rgba(0,210,255,0.25)!important}
.stButton>button{background:linear-gradient(135deg,#4831d4 0%,#6c5ce7 100%)!important;color:#fff!important;border:none!important;border-radius:12px!important;box-shadow:0 4px 12px rgba(72,49,212,0.3)!important;font-weight:600!important}
.stButton>button:hover{box-shadow:0 6px 20px rgba(72,49,212,0.5)!important;transform:translateY(-1px)!important}
.scroll-box{max-height:280px;overflow-y:auto;padding:8px 12px;border:1px solid rgba(72,49,212,0.2);border-radius:12px;background:rgba(10,12,20,0.6);margin:6px 0}
.scroll-box pre{max-height:200px;overflow:auto;background:rgba(0,0,0,0.3);border-radius:8px;padding:10px;font-size:0.85em;position:relative}
.scroll-box code{font-size:0.85em}
.copy-btn{position:absolute;top:6px;right:6px;background:rgba(72,49,212,0.8);color:#fff;border:none;border-radius:6px;padding:2px 8px;font-size:0.75em;cursor:pointer;opacity:0;transition:opacity 0.2s}
.scroll-box:hover .copy-btn{opacity:1}
.regenerate-btn{background:transparent!important;border:1px solid rgba(72,49,212,0.3)!important;color:#8899aa!important;box-shadow:none!important;font-size:0.8em!important}
.suggest-btn{background:rgba(72,49,212,0.1)!important;border:1px solid rgba(72,49,212,0.2)!important;color:#8899aa!important;box-shadow:none!important;font-size:0.8em!important;text-align:left!important}
input[type="text"],input[type="password"]{background:rgba(15,18,30,0.8)!important;border:1px solid rgba(72,49,212,0.3)!important;border-radius:10px!important;color:#e0e6ed!important}
[data-testid="stStatusWidget"]{position:fixed!important;bottom:24px!important;right:24px!important;top:auto!important;z-index:999}
[data-testid="stStatusWidget"] button{border-radius:24px!important;padding:8px 20px!important}
</style>

<script>
// Ctrl+Enter 发送消息
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (input && input.value.trim()) {
            var btn = document.querySelector('[data-testid="stChatInput"] button');
            if (btn) btn.click();
        }
    }
});
</script>

""", unsafe_allow_html=True)

if st.session_state.get("theme", "dark") == "light":
    st.markdown("""
<style>
.stApp::before{background:linear-gradient(135deg,#f0f4f8 0%,#e8edf5 30%,#f5f7fa 60%,#f0f4f8 100%)!important}
.stApp::after{display:none}
.stApp,.stMarkdown,p,li,label,div{color:#1a1a2e!important}
h1,h2,h3{color:#1a1a2e!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(255,255,255,0.95)0%,rgba(245,247,250,0.92)40%,rgba(255,255,255,0.95)100%)!important;border-right:1px solid rgba(0,0,0,0.08)!important}
.agent-bubble{border:1px solid rgba(0,0,0,0.1)!important;background:rgba(255,255,255,0.9)!important;color:#1a1a2e!important}
.user-bubble{background:linear-gradient(135deg,#4831d4 0%,#6c5ce7 100%)!important;color:#fff!important}
.stChatInput textarea{background:rgba(255,255,255,0.9)!important;border-color:rgba(0,0,0,0.2)!important;color:#1a1a2e!important}
input[type="text"],input[type="password"]{background:rgba(255,255,255,0.9)!important;border-color:rgba(0,0,0,0.2)!important;color:#1a1a2e!important}
</style>

<script>
// Ctrl+Enter 发送消息
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (input && input.value.trim()) {
            var btn = document.querySelector('[data-testid="stChatInput"] button');
            if (btn) btn.click();
        }
    }
});
</script>

""", unsafe_allow_html=True)

# ============================================================
# Session State
# ============================================================
for k,d in [("logged_in",False),("user_id",None),("username",""),("chat_messages",[]),("show_register",False),("confirm_delete",None),("tool_list_cache",None),("theme","dark"),("streaming",True)]:
    if k not in st.session_state: st.session_state[k]=d

# ============================================================
# Agent Engine
# ============================================================
@st.cache_resource
def get_client():
    from openai import AsyncOpenAI
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key: raise RuntimeError("DEEPSEEK_API_KEY 未设置，请在 .env 中配置")
    return AsyncOpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"))

@st.cache_resource(ttl=3600)  # 缓存 1 小时，刷新秒开
def get_registry():
    from agent.tool_register import ToolRegistry
    from agent_platform.web_search import web_search
    from agent_platform.web_fetch import fetch_page
    from agent_platform.code_exec import execute_python
    from pydantic import BaseModel, Field

    class S(BaseModel): query: str = Field(description="搜索关键词")
    class F(BaseModel): url: str = Field(description="URL"); max_length: int = Field(default=2000)
    class C(BaseModel): expression: str = Field(description="数学表达式")
    class E(BaseModel): code: str = Field(description="Python 代码"); timeout: int = Field(default=10)

    def _calc(e):
        e=e.replace("^","**")
        try: return str(eval(e,{"__builtins__":{}}))
        except: return f"Error:{e}"

    reg = ToolRegistry()
    reg.register("web_search","互联网搜索",web_search,S)
    reg.register("fetch_page","抓取网页正文",fetch_page,F)
    reg.register("calculator","数学计算",_calc,C)
    reg.register("execute_python","执行 Python 代码并返回结果。可以写算法、数据分析、画图",execute_python,E)

    # RAG: 搜索本地学习笔记（首次建索引，后续从缓存加载）
    try:
        from rag_system.embedder import Embedder
        from rag_system.vector_store import VectorStore
        from rag_system.loader import DocumentLoader
        import numpy as np, pickle

        VECTOR_PATH = DATA_DIR / "route_vectors.npy"
        META_PATH = DATA_DIR / "route_meta.json"
        STORE_PATH = DATA_DIR / "route_store.pkl"

        # 检查 route/ 目录是否比缓存新（自动刷新索引）
        route_dir = Path(__file__).parent.parent.parent.parent / "route"
        need_rebuild = False
        if STORE_PATH.exists() and route_dir.exists():
            cache_mtime = STORE_PATH.stat().st_mtime
            for f in route_dir.glob("*.md"):
                if f.stat().st_mtime > cache_mtime:
                    need_rebuild = True
                    break

        if STORE_PATH.exists() and not need_rebuild:
            with open(STORE_PATH, "rb") as f:
                store = pickle.load(f)
            with open(META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
        else:
            loader = DocumentLoader(directory=str(Path(__file__).parent.parent.parent.parent / "route"))
            docs = loader.load_all()
            embedder = Embedder()
            chunks = []
            for d in docs:
                for i in range(0, max(1, len(d.content)//300), 1):
                    chunk = d.content[i*300:(i+3)*300]
                    if len(chunk) > 50:
                        chunks.append({"text": chunk, "source": d.metadata.get("source","?")})
            vectors = embedder.embed([c["text"] for c in chunks])
            store = VectorStore(dimension=vectors.shape[1])
            store.add([v.astype(np.float32) for v in vectors], list(range(len(chunks))))
            meta = chunks
            np.save(VECTOR_PATH, np.array(vectors))
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)
            with open(STORE_PATH, "wb") as f:
                pickle.dump(store, f)

            # 缓存 Embedder 避免每次搜索都加载 384MB 模型
            _embedder_cache = Embedder()

            def search_knowledge(query: str) -> str:
                try:
                    qv = _embedder_cache.embed([query])[0]
                    results = store.query(qv.astype(np.float32), top_k=3)
                    lines = []
                    for r in results:
                        m = meta[r["id"]]
                        lines.append(f"[{m['source']}] {m['text'][:300]}")
                    return "\n\n---\n".join(lines) if lines else "未找到相关内容"
                except Exception as e:
                    return f"知识库搜索失败: {e}"

            class KIn(BaseModel): query: str = Field(description="搜索关键词")
            reg.register("search_knowledge","搜索本地AI学习笔记(31篇)",search_knowledge,KIn)
    except Exception:
        pass

    # MCP 工具（自动检测 npx/uvx，失败不影响基础工具）
    try:
        from agent_platform.mcp_bridge import register_mcp_servers
        register_mcp_servers(reg)
    except Exception:
        pass
    return reg

def build_system_prompt(registry, username):
    base = registry.generate_system_prompt(
        f"你是 Nexus AI 助手。用户是 {username}。\n"
        "规则:\n"
        "1. 第一次 Action 先搜最相关的源，不要多轮探索\n"
        "2. 拿到足够信息后立即 Final Answer\n"
        "3. 同一工具+参数不重复调\n"
        "4. 工具失败直接基于已有知识回答\n"
        "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [markdown格式中文回答+引用来源]"
    )
    try:
        r = _supabase.table("users").select("id").eq("username",username).execute()
        if r.data:
            convs = load_convs(r.data[0]["id"], limit=6)
            if convs:
                lines = ["\n\n用户历史对话:"]
                for c in convs[-6:]:
                    lines.append(f"- [{c['created_at'][:16]}] Q:{c['question'][:60]}")
                base += "\n".join(lines)
    except: pass
    return base

async def run_agent(user_input, model, max_cycles, username):
    client = get_client(); registry = get_registry()
    if not st.session_state.tool_list_cache:
        st.session_state.tool_list_cache = registry.list_tools()
    sp = build_system_prompt(registry, username)
    msgs = [{"role":"system","content":sp},{"role":"user","content":user_input}]
    steps=[]; tools_used=[]; total_tokens=0; sources=[]; called_sigs=set()

    for cycle in range(max_cycles):
        resp = await client.chat.completions.create(model=model,messages=msgs,temperature=temperature)
        reply = resp.choices[0].message.content
        usage = resp.usage
        if usage: total_tokens += usage.total_tokens
        msgs.append({"role":"assistant","content":reply})

        if "Final Answer:" in reply:
            m = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
            final = m.group(1).strip() if m else reply
            return steps, sources, total_tokens, tools_used, final

        action = re.search(r"Action:\s*(\w+)", reply)
        inp = re.search(r"Action Input:\s*(\{.*?\})\s*$", reply, re.DOTALL)
        if not inp: inp = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

        if action:
            tn = action.group(1)
            try: args = json.loads(inp.group(1)) if inp else {}
            except: args = {}
            step = {"thought":reply[:250],"tool":tn,"args":str(args)[:120]}
            sig = f"{tn}|{json.dumps(args,sort_keys=True)}"
            if sig in called_sigs:
                observation = "警告:此工具+参数刚调用过,请勿重复。如信息足够请立即 Final Answer。"
            else:
                called_sigs.add(sig)
                try:
                    observation = registry.call(tn, **args)
                except Exception as e:
                    observation = f"工具调用失败: {e}。请换个工具或直接基于已有知识回答。"
            tools_used.append(tn)
            step["result"] = observation[:500]
            urls = re.findall(r"https?://[^\s\"\)]+", observation)
            for u in urls[:3]:
                if u not in [s["url"] for s in sources]:
                    sources.append({"tool":tn,"url":u})
            steps.append(step)
            obs_text = f"Observation:\n{observation}"
            n = len(steps)
            if n >= 3:
                obs_text += f"\n\n[系统提示] 已调用 {n} 次工具,信息已足够。请立即输出 Final Answer。"
            msgs.append({"role":"user","content":obs_text})
        else:
            return steps, sources, total_tokens, tools_used, reply
    return steps, sources, total_tokens, tools_used, "循环超限,请简化问题重试。"

# ============================================================
# Login Page
# ============================================================
if not st.session_state.logged_in:
    ca, cb, cc = st.columns([1,1.3,1])
    with cb:
        st.markdown("<br>", unsafe_allow_html=True)
        st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png",width=64)
        st.markdown("## Nexus AI Platform")
        if st.session_state.show_register:
            st.markdown("### 注册")
            with st.form("reg_form"):
                ru = st.text_input("用户名",placeholder="输入用户名")
                rp = st.text_input("密码",type="password",placeholder="输入密码（至少4位）")
                rp2 = st.text_input("确认密码",type="password",placeholder="再输一遍密码")
                c1,c2=st.columns(2)
                with c1:
                    if st.form_submit_button("注册",use_container_width=True):
                        if not ru or not rp: st.error("请填写完整")
                        elif rp!=rp2: st.error("两次密码不一致")
                        else:
                            ok,msg=register_user(sanitize(ru),rp)
                            if ok: st.session_state.show_register=False; st.success(msg); st.rerun()
                            else: st.error(msg)
                with c2:
                    if st.form_submit_button("返回登录",use_container_width=True):
                        st.session_state.show_register=False; st.rerun()
        else:
            st.markdown("### 登录")
            with st.form("login_form"):
                iu = st.text_input("用户名",placeholder="输入用户名")
                ip = st.text_input("密码",type="password",placeholder="输入密码")
                c1,c2=st.columns(2)
                with c1:
                    if st.form_submit_button("登  录",use_container_width=True):
                        if not iu or not ip: st.error("请输入用户名和密码")
                        else:
                            ok,msg,uid=login_user(sanitize(iu),ip)
                            if ok:
                                st.session_state.logged_in=True; st.session_state.user_id=uid
                                st.session_state.username=iu.strip()
                                convs = load_convs(uid, limit=1)
                                st.session_state.chat_messages = []
                                if convs:
                                    c = convs[0]
                                    st.session_state.chat_messages = [
                                        {"role":"user","content":c["question"]},
                                        {"role":"agent","content":c["answer"],"tools_used":json.loads(c["tools_used"]) if c["tools_used"] else [],"sources":json.loads(c["sources"]) if c["sources"] else [],"tokens":c["tokens"]},
                                    ]
                                st.rerun()
                            else: st.error(msg)
                with c2:
                    if st.form_submit_button("注册新用户",use_container_width=True):
                        st.session_state.show_register=True; st.rerun()
    st.stop()

# ============================================================
# Main UI
# ============================================================
col_u,col_t,col_s = st.columns([1.5,5,2])
with col_u:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;">
        <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#4831d4,#00d2ff);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;">{st.session_state.username[0].upper()}</div>
        <div><div style="font-weight:600;color:#fff;">{st.session_state.username}</div><div style="font-size:0.7em;color:#8899aa;">在线</div></div>
    </div>""", unsafe_allow_html=True)
with col_t:
    st.markdown('<p style="text-align:center;font-family:Orbitron;font-size:1.3em;color:#fff;margin:8px 0;">NEXUS AI</p>',unsafe_allow_html=True)
with col_s:
    tc = st.session_state.tool_list_cache
    tc_display = str(len(tc)) if tc else "..."
    st.markdown(f'<p style="text-align:right;font-size:0.75em;color:#667788;margin:8px 0;">{tc_display} tools</p>',unsafe_allow_html=True)
st.markdown('<div style="height:1px;background:linear-gradient(90deg,transparent,rgba(72,49,212,0.5),rgba(0,210,255,0.3),transparent);margin:4px 0;"></div>',unsafe_allow_html=True)

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown('<p style="font-family:Orbitron;font-size:1.2em;color:#00d2ff;text-align:center;">CONTROL PANEL</p>',unsafe_allow_html=True)

    # Theme toggle
    theme_label = " 暗" if st.session_state.theme=="dark" else " 明"
    if st.button(theme_label, use_container_width=True, help="切换明暗主题"):
        st.session_state.theme = "light" if st.session_state.theme=="dark" else "dark"
        st.rerun()

    st.markdown("### 模型")
    model = st.selectbox("选择模型",["deepseek-chat","deepseek-reasoner","deepseek-v4-pro","deepseek-v4-flash"],index=0,label_visibility="collapsed")
    max_cycles = st.slider("最大推理轮数",3,10,6)
    temperature = st.slider("温度",0.0,1.5,0.0,0.1,help="0=精确 1.5=创意")

    st.divider()
    st.markdown("### 可用工具")
    tool_list = st.session_state.tool_list_cache or []
    if st.button("加载工具列表", use_container_width=True, help="首次点击会连接 MCP + 建 RAG 索引，约30秒"):
        with st.spinner("连接 MCP Server + 建知识库索引..."):
            st.session_state.tool_list_cache = get_registry().list_tools()
        st.rerun()
    if tool_list:
        with st.expander(f"查看全部 ({len(tool_list)})", expanded=False):
            for t in tool_list:
                st.caption(f"  {t['name']}")
    else:
        st.caption("点击上方按钮加载")

    st.divider()
    st.markdown("### 会话统计")
    total_session_tokens = sum(m.get("tokens",0) for m in st.session_state.chat_messages if m["role"]=="agent")
    total_session_cost = total_session_tokens * 0.00001
    total_session_tools = sum(len(m.get("tools_used",[])) for m in st.session_state.chat_messages if m["role"]=="agent")
    st.metric("Token", total_session_tokens)
    st.metric("花费", f"¥{total_session_cost:.4f}")
    st.metric("工具调用", total_session_tools)
    st.metric("对话轮数", len(st.session_state.chat_messages)//2)

    st.divider()
    st.markdown("### 历史对话")
    cn, cc = st.columns(2)
    with cn:
        if st.button("新建",use_container_width=True):
            st.session_state.chat_messages=[]; st.rerun()
    with cc:
        if st.button("全部清空",use_container_width=True):
            st.session_state.confirm_delete="ALL"; st.rerun()
    if st.session_state.confirm_delete=="ALL":
        st.warning("确认删除全部历史?")
        a1,a2=st.columns(2)
        with a1:
            if st.button("确认",use_container_width=True):
                if st.session_state.user_id:
                    clear_convs(st.session_state.user_id); st.session_state.chat_messages=[]
                st.session_state.confirm_delete=None; st.rerun()
        with a2:
            if st.button("取消",key="noall",use_container_width=True):
                st.session_state.confirm_delete=None; st.rerun()

    if st.session_state.user_id:
        convs = load_convs(st.session_state.user_id,limit=15)
        if not convs: st.caption("暂无历史")
        for c in convs[-15:]:
            cid=c["id"]
            label=f"{c['created_at'][5:16]} | {c['question'][:25]}"
            cl,cd = st.columns([4,1])
            with cl:
                if st.button(label,key=f"l_{cid}",use_container_width=True):
                    st.session_state.chat_messages=[
                        {"role":"user","content":c["question"]},
                        {"role":"agent","content":c["answer"],"tools_used":json.loads(c["tools_used"]) if c["tools_used"] else [],"sources":json.loads(c["sources"]) if c["sources"] else [],"tokens":c["tokens"]},
                    ]; st.rerun()
            with cd:
                if st.button("",key=f"d_{cid}"):
                    st.session_state.confirm_delete=cid; st.rerun()
            if st.session_state.confirm_delete==cid:
                st.warning(f"删除: {c['question'][:40]}?")
                a1,a2=st.columns(2)
                with a1:
                    if st.button("删除",key=f"y_{cid}"):
                        del_conv(cid); st.session_state.confirm_delete=None; st.rerun()
                with a2:
                    if st.button("取消",key=f"n_{cid}"):
                        st.session_state.confirm_delete=None; st.rerun()

    st.divider()
    # 导出对话
    if st.session_state.chat_messages:
        export_text = f"# Nexus AI 对话记录\n\n用户: {st.session_state.username}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
        for m in st.session_state.chat_messages:
            if m["role"]=="user":
                export_text += f"## 用户\n\n{m['content']}\n\n"
            else:
                tokens = m.get("tokens",0)
                tools = m.get("tools_used",[])
                export_text += f"## Agent ({tokens} tokens"
                if tools:
                    export_text += f", 工具: {' → '.join(tools)}"
                export_text += f")\n\n{m['content']}\n\n"
                if m.get("sources"):
                    export_text += "**来源:**\n"
                    for s in m["sources"]:
                        export_text += f"- {s['url']}\n"
                    export_text += "\n"
                export_text += "---\n\n"
        st.download_button(" 导出对话 (Markdown)", export_text, file_name=f"nexus-chat-{datetime.now().strftime('%Y%m%d-%H%M')}.md", mime="text/markdown", use_container_width=True)

    if st.button("退出登录",use_container_width=True):
        for k in ["logged_in","user_id","username","chat_messages","confirm_delete"]:
            st.session_state[k]=False if k=="logged_in" else (None if k in ("user_id","confirm_delete") else "" if k=="username" else [])
        st.rerun()

# ============================================================
# Chat Area
# ============================================================
for msg in st.session_state.chat_messages:
    if msg["role"]=="user":
        st.markdown(f'<div class="user-bubble">{msg["content"]}</div>',unsafe_allow_html=True)
    else:
        st.markdown(msg["content"])
        tokens=msg.get("tokens",0); tools=msg.get("tools_used",[]); cost=tokens*0.00001
        parts=[]
        if tools: parts.append(f" {'→'.join(tools)}")
        if tokens: parts.extend([f" {tokens} tokens",f" ¥{cost:.4f}"])
        if parts: st.caption("|".join(parts))
        if msg.get("sources"):
            with st.expander(" 信息来源"):
                for s in msg["sources"]:
                    st.markdown(f'<div class="source-card"><a href="{s["url"]}" target="_blank" style="color:#00b0ff;">{s["url"][:90]}...</a></div>',unsafe_allow_html=True)

# ============================================================
# 模式选择
# ============================================================
mode_col1, mode_col2, mode_col3 = st.columns([2,2,6])
with mode_col1:
    agent_mode = st.radio("推理模式", ["标准", "Reflexion", "多路生成"], index=0,
                          horizontal=True, label_visibility="collapsed")
if agent_mode == "Reflexion":
    st.caption("Reflexion: Agent 回答后自我批判并修正")
elif agent_mode == "多路生成":
    st.caption("多路: 生成 3 种风格答案，你选最好的")
else:
    st.caption("标准: 一次推理直接回答")

# ============================================================
# 多路生成：用户选择界面
# ============================================================
if "pending_choices" not in st.session_state:
    st.session_state.pending_choices = None
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

# 显示待选答案
if st.session_state.pending_choices:
    st.divider()
    st.markdown("###  选择最佳答案")
    st.caption(f"问题: {st.session_state.pending_question}")

    choices = st.session_state.pending_choices
    border = "border:1px solid rgba(72,49,212,0.4);border-radius:16px;padding:14px;margin:4px 0;background:rgba(20,25,45,0.7);"

    def render_answer_section(c):
        content = c["answer"]
        parts = re.split(r'(```[^`]*```)', content)
        for part in parts:
            if part.startswith("```"):
                # 代码块进滚动框
                code = part.strip("`").strip()
                if "\n" in code and code[0].isalpha():
                    code = "\n".join(code.split("\n")[1:])
                code_escaped = code.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                st.markdown(f'<div class="scroll-box" style="max-height:200px;"><pre><code>{code_escaped[:2000]}</code></pre></div>',unsafe_allow_html=True)
            elif part.strip():
                st.markdown(part[:2000])
        if c.get("steps"):
            st.caption(f"  工具: {' → '.join(s.get('tool','?') for s in c['steps'])}")

    # 第一行：方案1 全宽
    c = choices[0]
    st.markdown(f"""<div style="{border}">
        <span style="color:#00d2ff;font-weight:700;"> 方案 A — {c['label']}</span>
        <span style="color:#667788;font-size:0.8em;"> | {c['tokens']} tokens</span>
        </div>""", unsafe_allow_html=True)
    render_answer_section(c)
    if st.button(f" 选方案 A — {c['label']}", key="pick_0", use_container_width=True):
        _chosen = choices[0]
        st.session_state.chat_messages.extend([
            {"role":"user","content":st.session_state.pending_question},
            {"role":"agent","content":f"**[{_chosen['label']}]**\n\n{_chosen['answer']}",
             "tools_used":[s.get("tool","") for s in _chosen.get("steps",[])],"tokens":_chosen["tokens"]},
        ])
        st.session_state.pending_choices=None; st.session_state.pending_question=""; st.rerun()

    # 第二行：方案2 + 方案3 并排
    col_l, col_r = st.columns(2)
    for idx, col in [(1, col_l), (2, col_r)]:
        c = choices[idx]
        label_letter = "B" if idx == 1 else "C"
        with col:
            st.markdown(f"""<div style="{border}">
                <span style="color:#00d2ff;font-weight:700;"> 方案 {label_letter} — {c['label']}</span>
                <span style="color:#667788;font-size:0.8em;"> | {c['tokens']} tokens</span>
                </div>""", unsafe_allow_html=True)
            render_answer_section(c)
            if st.button(f" 选方案 {label_letter} — {c['label']}", key=f"pick_{idx}", use_container_width=True):
                _chosen = choices[idx]
                st.session_state.chat_messages.extend([
                    {"role":"user","content":st.session_state.pending_question},
                    {"role":"agent","content":f"**[{_chosen['label']}]**\n\n{_chosen['answer']}",
                     "tools_used":[s.get("tool","") for s in _chosen.get("steps",[])],"tokens":_chosen["tokens"]},
                ])
                st.session_state.pending_choices=None; st.session_state.pending_question=""; st.rerun()

    if st.button(" 都不满意，用 Reflexion 重试", use_container_width=True):
        st.session_state.pending_choices = None
        st.rerun()
    st.divider()
    st.stop()

# ============================================================
# Input
# ============================================================
if prompt := st.chat_input("输入问题... Agent 将自主搜索、读文件、写代码..."):
    st.markdown(f'<div class="user-bubble">{prompt}</div>',unsafe_allow_html=True)

    # ---- 标准模式 ----
    if agent_mode == "标准":
        client = get_client(); registry = get_registry()
        sp = build_system_prompt(registry, st.session_state.username)
        msgs = [{"role":"system","content":sp},{"role":"user","content":prompt}]
        steps=[]; tools_used=[]; total_tokens=0; sources=[]; called_sigs=set()
        final = None

        # 流式输出容器
        stream_placeholder = st.empty()

        for cycle in range(max_cycles):
            # 调用 LLM（非流式，获取完整回复以解析 Action）
            resp = asyncio.run(client.chat.completions.create(
                model=model, messages=msgs, max_tokens=4096, temperature=temperature,
            ))
            reply = resp.choices[0].message.content
            if resp.usage: total_tokens += resp.usage.total_tokens
            msgs.append({"role":"assistant","content":reply})

            if "Final Answer:" in reply:
                m = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                final = m.group(1).strip() if m else reply
                break

            action = re.search(r"Action:\s*(\w+)", reply)
            inp = re.search(r"Action Input:\s*(\{.*?\})\s*$", reply, re.DOTALL)
            if not inp: inp = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if action:
                tn = action.group(1)
                try: args = json.loads(inp.group(1)) if inp else {}
                except: args = {}
                step = {"thought":reply[:250],"tool":tn,"args":str(args)[:120]}
                sig = f"{tn}|{json.dumps(args,sort_keys=True)}"
                if sig in called_sigs:
                    observation = "警告:此工具+参数刚调用过,请勿重复。"
                else:
                    called_sigs.add(sig)
                    try:
                        observation = registry.call(tn, **args)
                    except Exception as e:
                        observation = f"工具调用失败: {e}。请换工具或直接回答。"
                tools_used.append(tn); step["result"] = observation[:500]; steps.append(step)

                # 实时展示工具调用
                with stream_placeholder.container():
                    st.markdown(f'<div class="thought-card">💭 {step["thought"]}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="tool-card">🔧 {tn} ( {step["args"]} )</div>',unsafe_allow_html=True)
                    st.caption(step.get("result","")[:400])

                obs_text = f"Observation:\n{observation}"
                n = len(steps)
                if n >= 3:
                    obs_text += f"\n\n[系统提示]已调用{n}次,请立即 Final Answer。"
                msgs.append({"role":"user","content":obs_text})
            else:
                final = reply; break

        if final is None:
            final = "循环超限,请简化问题重试。"

        # SDK 流式渲染最终答案
        async def stream_final():
            # 传完整上下文（含工具结果）
            ctx = msgs + [{"role":"user","content":"请基于以上信息给出完整中文 Final Answer："}]
            stream = await client.chat.completions.create(
                model=model, messages=ctx, stream=True, max_tokens=4096, temperature=temperature,
            )
            collected = ""; prefix_stripped = False
            async for chunk in stream:
                c = chunk.choices[0].delta.content or ""
                collected += c
                if not prefix_stripped:
                    body = collected.split("Final Answer:", 1)[-1].lstrip()
                    if body and body != collected.lstrip():
                        prefix_stripped = True
                        yield body
                    elif len(collected) > len("Final Answer:"):
                        prefix_stripped = True
                        yield collected
                else:
                    yield c  # 只出增量，不累积

        stream_placeholder.empty()
        try:
            result = stream_placeholder.write_stream(stream_final())
            if result and len(result.strip()) > 10:
                clean = re.sub(r'^["\s]*Final Answer:\s*', '', result.strip(), flags=re.IGNORECASE)
                clean = clean.replace("**Final Answer:**", "").replace("Final Answer:", "").strip()
                final = clean if clean else final
        except Exception:
            pass

        parts=[]
        if tools_used: parts.append(f" {'→'.join(tools_used)}")
        if total_tokens: parts.extend([f" {total_tokens} tokens",f" ¥{total_tokens*0.00001:.4f}"])
        if parts: st.caption("|".join(parts))
        if sources:
            with st.expander(" 信息来源"):
                for s in sources:
                    st.markdown(f'<div class="source-card"><a href="{s["url"]}" target="_blank" style="color:#00b0ff;">{s["url"][:90]}...</a></div>',unsafe_allow_html=True)
        for step in steps:
            with st.expander(f" {step['tool']} — {step['thought'][:60]}...", expanded=True):
                st.markdown(f'<div class="thought-card">{step["thought"]}</div>',unsafe_allow_html=True)
                st.markdown(f'<div class="tool-card"> {step["tool"]} ( {step["args"]} )</div>',unsafe_allow_html=True)
                st.caption(step.get("result","")[:600])
        st.session_state.chat_messages.extend([
            {"role":"user","content":prompt},
            {"role":"agent","content":final,"tools_used":tools_used,"sources":sources,"tokens":total_tokens},
        ])
        if st.session_state.user_id and final and "循环超限" not in final:
            save_conv(st.session_state.user_id,prompt,final,tools_used,total_tokens,sources)
        # 重新生成按钮（在回答最下方）
        st.divider()
        if st.button(" 重新生成", key=f"regen_{len(st.session_state.chat_messages)}", use_container_width=True):
            if len(st.session_state.chat_messages) >= 2:
                st.session_state.chat_messages.pop()
                st.session_state.chat_messages.pop()
            st.rerun()

    # ---- Reflexion 模式 ----
    elif agent_mode == "Reflexion":
        from agent_platform.advanced import reflexion_answer
        with st.spinner("Reflexion: 生成初稿..."):
            result = asyncio.run(reflexion_answer(get_client(), get_registry(), prompt, max_cycles, temperature))
        # 三栏：初稿 | 批判 | 修正
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<span style="color:#ff9800;font-weight:700;"> 初稿</span>',unsafe_allow_html=True)
            st.markdown(result["draft"][:1500])
            if result["steps"]:
                st.caption(f"  工具: {len(result['steps'])}次")
        with c2:
            st.markdown('<span style="color:#00b0ff;font-weight:700;"> 自我批判</span>',unsafe_allow_html=True)
            st.markdown(result["critique"][:1500])
        with c3:
            st.markdown('<span style="color:#00c853;font-weight:700;"> 修正后</span>',unsafe_allow_html=True)
            st.markdown(result["answer"][:2000])
        st.caption(f"{result['tokens']} tokens | ¥{result['tokens']*0.00001:.4f}")
        st.session_state.chat_messages.extend([
            {"role":"user","content":prompt},
            {"role":"agent","content":result["answer"],
             "tools_used":[s.get("tool","") for s in result.get("steps",[])],"tokens":result["tokens"]},
        ])
        if st.session_state.user_id:
            save_conv(st.session_state.user_id,prompt,result["answer"],
                      [s.get("tool","") for s in result.get("steps",[])],result["tokens"],[])

    # ---- 多路生成模式 ----
    else:
        from agent_platform.advanced import multi_path_answer
        with st.spinner("多路生成: 同时跑 3 种风格..."):
            choices = asyncio.run(multi_path_answer(get_client(), get_registry(), prompt, max_cycles, temperature))
        st.session_state.pending_choices = choices
        st.session_state.pending_question = prompt

    st.rerun()
