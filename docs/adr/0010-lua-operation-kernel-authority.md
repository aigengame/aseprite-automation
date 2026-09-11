---
status: accepted
---

# Make the Lua Operation Kernel the authority for core operation behavior

The versioned, packaged Lua Operation Kernel is the sole authority for the Core Operation Semantics of every ordinary Operation. One fixed handler defines what that Operation creates, edits, observes, validates, converts, or exports through Aseprite's native model and API. Standalone execution and Operation Plan execution invoke the same handler.

The Python Application Layer owns the public automation contract and use-case orchestration: Operation Descriptors, request/result/failure schemas, static Preflight, Execution Kind, Plan Step admission, public failure mapping, access-channel projection, selection and ordering of packaged Kernel capabilities, Aseprite invocation structure, staged file commit, and Artifact reporting. It may compose fixed handlers through private Kernel Protocol data when an accepted use case requires several capabilities. Those responsibilities do not authorize Python entrypoints, adapters, or Plan code to reproduce a handler's editing, observation, conversion, rendering, or encoding algorithm.

The Lua Kernel owns behavior that depends on Aseprite's live model: resolving each Operation's target fields against the current Sprite, enforcing its Step Preconditions and target-count rules, applying native document mutations inside `app.transaction`, observing native objects and pixels, invoking supported Aseprite conversion or export behavior, and producing the private protocol response. Python validates and translates that response without simulating the Aseprite behavior that produced it.

SPA never assembles or generates Lua source at runtime to implement an ordinary Operation. Runtime values cross the boundary as data in request and response files referenced by `--script-param`. Temporary request, response, staging, and diagnostic files are allowed because they contain data or artifacts; they do not become executable behavior. Ordinary handlers and their shared helpers are packaged, versioned, reviewable source files.

The Operation Descriptor remains the single public registration and contract-projection authority. It binds an Operation to its packaged Lua entry handler but does not become a second behavior implementation. The Application Layer may build a private ordered execution that selects or composes packaged capabilities; when those steps share a live Sprite, one Aseprite process dispatches them through the Lua Kernel against the same document. This private structure is not a caller-visible workflow language. Parity tests prove every descriptor binding resolves to packaged handlers, every native step reaches its Lua authority, and standalone, Plan, and composed use-case paths do not substitute Python implementations.

Caller-supplied raw Lua is a separate `script-run` capability governed by ADR-0011. It is not an ordinary Operation implementation and cannot be used internally to bypass the packaged Kernel.
