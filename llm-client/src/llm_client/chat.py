from dataclasses import dataclass, field
from openai import AsyncOpenAI
from collections.abc import AsyncGenerator
import tiktoken

@dataclass
class ChatSession:
    """一次多轮对话"""

    client: AsyncOpenAI
    model: str
    system_prompt: str
    history: list[dict] = field(default_factory=list)
    max_history_tokens: int = 4000

    _encoder : tiktoken.Encoding = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._encoder = tiktoken.get_encoding("cl100k_base")  # 适用于 gpt-4 和 gpt-3.5-turbo
        self.history.append({"role": "system", "content": self.system_prompt})
    
    def _count_tokens(self) -> int:
        """计算当前历史消息的 token 数量。"""
        total_tokens = 0
        for msg in self.history:
            total_tokens += len(self._encoder.encode(msg["content"]))
        return total_tokens
    
    def _trim_history(self) -> None:
        """如果历史消息超过 token 限制，就删除最早的用户/助手消息（保留 system）。"""
        while self._count_tokens() > self.max_history_tokens and len(self.history) > 1:
            # 删除第二条消息（第一条是 system）
            removed = self.history.pop(1)
            print(f"  [历史消息过多，已删除] {removed['role']}: {removed['content'][:30]}...")

    async def send(self, user_message: str) -> str:
        #1. 把用户消息添加到历史
        self.history.append({"role": "user", "content": user_message})
        self._trim_history()  # 确保历史消息不超过 token 限制

        #2. 调用 API 获取回复
        response = await self.client.chat.completions.create(
            model = self.model,
            messages = self.history,
        )

        #3. 提取恢复内容
        reply = response.choices[0].message.content

        #4. 把回复添加到历史
        self.history.append({"role": "assistant", "content": reply})
        
        return reply
    @property
    def message_count(self) -> int:
        return len(self.history) - 1
    
    async def send_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """流式发送消息——每生成一个 chunk 就 yield 出去。

        调用方可以 async for chunk in session.send_stream("你好"):
            print(chunk, end="")  实时显示
        """
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        stream = await self.client.chat.completions.create(
            model = self.model,
            messages = self.history,
            stream = True
        )    

        full_reply = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_reply += delta.content
                yield delta.content
        self.history.append({"role": "assistant", "content": full_reply})
        
    async def send_with_tools(self, user_input: str, tools: list) -> str:
        """发送消息并调用工具（如果模型回复里有工具调用指令）。"""
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        # 1. 模型是否决定调用工具
        response = await self.client.chat.completions.create(
            model = self.model,
            messages = self.history,
            tools = [t.to_openai_schema() for t in tools]
        )

        msg = response.choices[0].message

        # 如果模型要求调用工具
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                print(f"模型要求调用工具: {tool_name}，参数: {tool_args}")

                tool = next((t for t in tools if t.name == tool_name), None)
                result = tool.run(tool_args) if tool else f"错误：未找到工具 {tool_name}"

                # 把工具调用和结果加入历史
                self.history.append({
                    "role": "assistant",
                    "tool_calls": [{"id": tool_call.id, "type": "function",
                                    "function": {"name": tool_name, "arguments": tool_args}}],
                    "content": "",
                })
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            response = await self.client.chat.completions.create(
                model = self.model,
                messages = self.history,
            )
            msg = response.choices[0].message
        reply = msg.content
        self.history.append({"role": "assistant", "content": reply})
        return reply    
    
    async def send_stream_with_tools(self, user_input: str, tools: list) -> AsyncGenerator[str, None]:
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        response = await self.client.chat.completions.create(
            model = self.model,
            messages = self.history,
            tools = [t.to_openai_schema() for t in tools],
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                tool = next((t for t in tools if t.name == tool_name), None)
                result = tool.run(tool_args) if tool else f"错误：未找到工具 {tool_name}"

                print(f"模型要求调用工具: {tool_name}，参数: {tool_args}，结果: {result}")

                self.history.append({
                    "role": "assistant",
                    "tool_calls": [{"id": tool_call.id, "type": "function",
                                    "function": {"name": tool_name, "arguments": tool_args}}],
                    "content": "",
                })
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            stream = await self.client.chat.completions.create(
                model = self.model,
                messages = self.history,
                stream = True,
            )
            full_reply = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_reply += chunk.choices[0].delta.content
                    yield chunk.choices[0].delta.content
            self.history.append({"role": "assistant", "content": full_reply})
        else:
            self.history.pop()  # 没有工具调用的话，先把用户消息从历史里去掉，等流式回复完再加回去（保持历史里都是完整消息）
            async for chunk in self.send_stream(user_input):
                yield chunk