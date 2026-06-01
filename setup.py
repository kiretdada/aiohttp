import os
import pathlib
import sys

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

if sys.version_info < (3, 10):
    raise RuntimeError("aiohttp 4.x requires Python 3.10+")


USE_SYSTEM_DEPS = bool(
    os.environ.get("AIOHTTP_USE_SYSTEM_DEPS", os.environ.get("USE_SYSTEM_DEPS"))
)
NO_EXTENSIONS: bool = bool(os.environ.get("AIOHTTP_NO_EXTENSIONS"))
CYTHON_TRACING: bool = bool(os.environ.get("AIOHTTP_CYTHON_TRACE"))
HERE = pathlib.Path(__file__).parent
IS_GIT_REPO = (HERE / ".git").exists()


if sys.implementation.name != "cpython":
    NO_EXTENSIONS = True


if not USE_SYSTEM_DEPS:
    llhttp_required_files = (
        HERE / "vendor/llhttp/build/llhttp.h",
        HERE / "vendor/llhttp/build/c/llhttp.c",
        HERE / "vendor/llhttp/src/native/api.c",
        HERE / "vendor/llhttp/src/native/http.c",
    )
    if not all(path.exists() for path in llhttp_required_files):
        NO_EXTENSIONS = True
        print(
            "llhttp sources are missing; falling back to pure-python build.",
            file=sys.stderr,
        )
        if IS_GIT_REPO:
            print("Hint:", file=sys.stderr)
            print("  git submodule update --init", file=sys.stderr)
            print("  make generate-llhttp", file=sys.stderr)

c_extensions_required_files = (
    HERE / "aiohttp/_find_header.c",
    HERE / "aiohttp/_http_parser.c",
    HERE / "aiohttp/_http_writer.c",
    HERE / "aiohttp/_websocket/mask.c",
    HERE / "aiohttp/_websocket/reader_c.c",
)
if not NO_EXTENSIONS and not all(path.exists() for path in c_extensions_required_files):
    NO_EXTENSIONS = True
    print(
        "Generated C sources are missing; falling back to pure-python build.",
        file=sys.stderr,
    )


# NOTE: makefile cythonizes all Cython modules

if USE_SYSTEM_DEPS:
    import shlex

    import pkgconfig

    llhttp_sources = []
    llhttp_kwargs = {
        "extra_compile_args": shlex.split(pkgconfig.cflags("libllhttp")),
        "extra_link_args": shlex.split(pkgconfig.libs("libllhttp")),
    }
else:
    llhttp_sources = [
        "vendor/llhttp/build/c/llhttp.c",
        "vendor/llhttp/src/native/api.c",
        "vendor/llhttp/src/native/http.c",
    ]
    llhttp_kwargs = {
        "define_macros": [("LLHTTP_STRICT_MODE", 0)],
        "include_dirs": ["vendor/llhttp/build"],
    }

cython_trace_macros = [("CYTHON_TRACE", 1)] if CYTHON_TRACING else []
if cython_trace_macros:
    llhttp_kwargs.setdefault("define_macros", []).extend(cython_trace_macros)

extensions = [
    Extension(
        "aiohttp._websocket.mask",
        ["aiohttp/_websocket/mask.c"],
        define_macros=cython_trace_macros,
    ),
    Extension(
        "aiohttp._http_parser",
        [
            "aiohttp/_http_parser.c",
            "aiohttp/_find_header.c",
            *llhttp_sources,
        ],
        **llhttp_kwargs,
    ),
    Extension(
        "aiohttp._http_writer",
        ["aiohttp/_http_writer.c"],
        define_macros=cython_trace_macros,
    ),
    Extension(
        "aiohttp._websocket.reader_c",
        ["aiohttp/_websocket/reader_c.c"],
        define_macros=cython_trace_macros,
    ),
]


class ParallelBuildExt(build_ext):
    def build_extensions(self) -> None:
        if self.parallel is None:
            self.parallel = os.cpu_count() or 1
        super().build_extensions()


build_type = "Pure" if NO_EXTENSIONS else "Accelerated"
setup_kwargs = (
    {}
    if NO_EXTENSIONS
    else {"ext_modules": extensions, "cmdclass": {"build_ext": ParallelBuildExt}}
)

print("*********************", file=sys.stderr)
print("* {build_type} build *".format_map(locals()), file=sys.stderr)
print("*********************", file=sys.stderr)
setup(**setup_kwargs)
