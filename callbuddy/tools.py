"""All of Call Buddy's tools in one place: look_at_screen (+ Gmail tools when connected).

Concept: the LLM can't do anything by itself. We describe functions ("tools") with a name, a
description and parameters; when the LLM asks for one, Pipecat calls our handler and gives the
result back to the LLM, which then answers out loud.

cancel_on_interruption=False: if you say "hello" or a stray noise is transcribed while a tool
is running, the tool still finishes and the answer still comes (notes/failures.md #10).
"""

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema

from callbuddy import gmail as gm
from callbuddy.screen import LOOK_AT_SCREEN_SPEC, ScreenStore, look_at_screen


def register_tools(llm, *, vision_client, vision_model: str, store: ScreenStore, gmail=None) -> ToolsSchema:
    specs = [LOOK_AT_SCREEN_SPEC]

    async def screen_handler(params):
        q = dict(params.arguments).get("question", "")
        await params.result_callback(await look_at_screen(vision_client, vision_model, q, store))

    llm.register_function("look_at_screen", screen_handler, cancel_on_interruption=False)

    if gmail is not None:
        for spec in gm.TOOL_SPECS:

            async def handler(params, _name=spec["name"]):
                await params.result_callback(await gm.run_tool(gmail, _name, dict(params.arguments)))

            llm.register_function(spec["name"], handler, cancel_on_interruption=False)
            specs.append(spec)

    return ToolsSchema(standard_tools=[FunctionSchema(**s) for s in specs])
