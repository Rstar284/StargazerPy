import io
import os
import re
import zlib
import aiohttp
import discord
from discord.ext import commands
import json
from cogs.utils import db, fuzzy
import requests
import logging
url_tt = str.maketrans({
    ')': '\\)'
})
err_regex = re.compile(r"^error(\[.*\])*:", re.MULTILINE)
log = logging.getLogger(__name__)

class Text(commands.Converter):
    async def convert(self, ctx, argument):
        ret = argument
        return ret

class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class RTFM(db.Table):
    id = db.PrimaryKeyColumn()
    user_id = db.Column(db.Integer(big=True), unique=True, index=True)
    count = db.Column(db.Integer, default=1)

class Obj(dict):
    # This is a dictionary which you can access using . instead of [].
    # Nice for JSON data.
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

class CodeBlock:
    missing_error = "Missing code block. Please use the following markdown\n\\`\\`\\`rust\ncode here\n\\`\\`\\`"

    def __init__(self, argument):
        try:
            block, code = argument.split("\n", 1)
        except ValueError:
            raise commands.BadArgument(self.missing_error)

        if not block.startswith("```") and not code.endswith("```"):
            raise commands.BadArgument(self.missing_error)

        self.source = code.rstrip("`")


class CodeSection:
    missing_error = "Missing code section. Please use the following markdown\n\\`code here\\`\nor\n\\`\\`\\`rust\ncode here\n\\`\\`\\`"

    def __init__(self, code):
        codeblock = code.startswith("```") and code.endswith("```")
        codesection = code.startswith("`") and code.endswith("`")
        if not codesection and not codeblock:
            raise commands.BadArgument(self.missing_error)

        if codeblock:
            self.source = "\n".join(code.split("\n")[1:]).rstrip("`")
        else:
            self.source = code.strip("`")

class Coding(commands.Cog):
    """
    Provides utilities for help in coding *Me* or any *other* bot or just coding in general
    """
    def __init__(self, bot):
        self.bot = bot
        self.issue = re.compile(r'##(?P<number>[0-9]+)')
        self._recently_blocked = set()
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.sent_evals = {}

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        
    def transform_rtfm_language_key(self, ctx, prefix):
        if ctx.guild is not None:
            #                             日本語 category
            if ctx.channel.category_id == 490287576670928914:
                return prefix + '-jp'
            #                    d.py unofficial JP   Discord Bot Portal JP
            elif ctx.guild.id in (463986890190749698, 494911447420108820):
                return prefix + '-jp'
        return prefix

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            sub = cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_rtfm(self, ctx, key, obj):
        page_types = {
            'latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
        }

        if obj is None:
            await ctx.send(page_types[key])
            return

        if not hasattr(self, '_rtfm_cache'):
            await ctx.trigger_typing()
            await self.build_rtfm_lookup_table(page_types)

        obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

        if key.startswith('latest'):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = f'abc.Messageable.{name}'
                    break

            cache = list(self._rtfm_cache[key].items())

            def transform(tup):
                return tup[0]

            matches = fuzzy.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

            e = discord.Embed(colour=discord.Colour.blurple())
            if len(matches) == 0:
                return await ctx.send('Could not find anything. Sorry.')

            e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
            await ctx.send(embed=e, reference=ctx.replied_reference)

    @commands.command()
    async def dpydoc(self, ctx, *, obj: str = None):
        """Gives you a documentation link for a discord.py entity.
        Events, objects, and functions are all avalible with the command
        """
        key = self.transform_rtfm_language_key(ctx, 'latest')
        await self.do_rtfm(ctx, key, obj)

    @commands.command(name='pythondoc', aliases=['pydoc'])
    async def rtfm_python(self, ctx, *, obj: str = None):
        """Gives you a documentation link for a Python entity."""
        key = self.transform_rtfm_language_key(ctx, 'python')
        await self.do_rtfm(ctx, key, obj)
    
    @commands.command(name='mdn')
    async def cmd_mdn(self, ctx, *search_terms: str):
        """
        Search the Mozilla Developer Network
        """
        async with self.session.get(
            'https://developer.mozilla.org/api/v1/search/en-US',
            params={'q': ' '.join(search_terms)},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            result = json.loads(await response.text(), object_hook=Obj)


        embed = discord.Embed(
            colour=getattr(ctx.me, 'color', 0),
            description='\n'.join(
                f'**[{doc.title}]({f"https://developer.mozilla.org/{doc.locale}/docs/{doc.slug}".translate(url_tt)})**\n{doc.summary}\n'
                for doc in result.documents[:3]
            )
        )

        embed.set_author(
            name="Mozilla Developer Network [Full results]",
            url=f'https://developer.mozilla.org/en-US/search?q={"+".join(search_terms)}',
            icon_url="https://developer.mozilla.org/static/img/opengraph-logo.72382e605ce3.png"
        )

        await ctx.send(embed=embed)
    
    @commands.command(name="createhb")
    async def haste(self,ctx, language: str = None,*,text: commands.Greedy[Text]):
        hatebinurl = "https://haste-server-rstar.herokuapp.com"
        textinput = text
        if text == "":
            await ctx.reply("NO text to put in the paste? WHY")
            return
        r = requests.post('%s/documents' % hatebinurl, textinput.encode('utf8'))
        url = '%s/%s' % (hatebinurl, json.loads(r.content.decode())['key'])
        if language == None:
            embed = discord.Embed(
                title="Hastebin Url Response",
                description="The paste url is " + url
            )
            embed.set_image(url="https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Ftse1.mm.bing.net%2Fth%3Fid%3DOIP.i-5wFHjtuMp1hBQq4j20kgAAAA%26pid%3DApi%26h%3D160&f=1")
            await ctx.send(embed=embed)
        elif language != None:
            embed = discord.Embed(
                title="Hastebin Url Response",
                description="The paste url is " + url + "." + language.lower()
            )
            embed.set_image(url="https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Ftse1.mm.bing.net%2Fth%3Fid%3DOIP.i-5wFHjtuMp1hBQq4j20kgAAAA%26pid%3DApi%26h%3D160&f=1")
            await ctx.send(embed=embed)
'''
    @commands.command()
    async def rustrun(self, ctx: commands.Context, code):
        """Evaluates Rust code with an optional compilation mode.
        Defaults to debug.
        Usage:
        ?rustrun (--release|--debug) ```rs
        <your Rust code here>
        ```
        """
        (mode, code) = self.parse_args(code)
        comment_index = code.source.find("//")
        end_idx = comment_index if comment_index != -1 else len(code.source)
        await self.send_playground(
            ctx, mode, 'fn main(){println!("{:?}",{' + code.source[:end_idx] + "});}"
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        sent_eval_id = self.sent_evals.get(before.id, None)
        if sent_eval_id is not None:
            ctx: commands.Context = await self.bot.get_context(after)
            if not ctx.valid:
                return

            try:
                sent_eval = await ctx.fetch_message(sent_eval_id)

                await ctx.command.prepare(ctx)

                # 'arg' depends on the name of the argument in the commands above; they must all at least be the same,
                # and if they change, this must be changed too. Messy, but arguments are only provided as a dict.
                (mode, code) = self.parse_args(ctx.kwargs["arg"])

                warnings = False
                if ctx.command.name == "eval":
                    comment_index = code.source.find("//")
                    end_idx = comment_index if comment_index != -1 else len(code.source)
                    code.source = (
                        'fn main(){println!("{:?}",{' + code.source[:end_idx] + "});}"
                    )
                elif ctx.command.name == "playwarn":
                    warnings = True
                elif ctx.command.name != "play":
                    return

                await self.edit_playground(ctx, sent_eval, mode, code.source, warnings)
            except (
                discord.HTTPException,
                discord.Forbidden,
                commands.MissingRequiredArgument,
                commands.CommandError,
            ) as e:
                await self.cog_command_error(ctx, e)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self.sent_evals.pop(message.id, None)

    def parse_args(self, args):
        args = args.replace("\n`", " `").split(" ")
        if args[0].startswith("--"):
            mode = args[0][2:]
            mode.strip()
            code = " ".join(args[1:])
            if mode != "release" and mode != "debug":
                raise commands.BadArgument(
                    "Bad compile mode. Valid options are `--release` and `--debug`"
                )

            return mode, CodeSection(code)
        else:
            code = " ".join(args[0:])
            return None, CodeSection(code)

    async def edit_playground(
        self, ctx: commands.Context, sent_message, mode, code, warnings: bool = False
    ):
        async with ctx.typing():
            await sent_message.edit(
                content=await self.query_playground(mode, code, warnings)
            )

    async def send_playground(
        self, ctx: commands.Context, mode, code, warnings: bool = False
    ):
        async with ctx.typing():
            sent_message = await ctx.send(
                await self.query_playground(mode, code, warnings)
            )

        self.sent_evals[ctx.message.id] = sent_message.id

    async def query_playground(self, mode, code, warnings: bool = False):
        payload = json.dumps(
            {
                "channel": "nightly",
                "edition": "2018",
                "code": code,
                "crateType": "bin",
                "mode": mode if mode is not None else "debug",
                "tests": False,
            }
        )

        async with self.session.post(
            "https://play.rust-lang.org/execute", data=payload
        ) as r:
            if r.status != 200:
                raise commands.CommandError(
                    "Rust Playground didn't respond in time. :("
                )

            response = await r.json()
            if "error" in response:
                raise commands.CommandError(response["error"])

            stderr = response["stderr"]
            stdout = response["stdout"]

            full_response = (
                stdout
                if err_regex.search(stderr) is None
                and not (warnings and len(stderr) >= 4)
                and "panicked" not in stderr
                else "\n".join(stderr.split("\n")[1:]) + "\n\n" + stdout
            )
            len_response = len(full_response)
            if len_response == 0:
                msg = "``` ```"
            elif len_response < 1990:
                full_response = full_response.replace("```", "  ̀  ̀  ̀")
                msg = f"```rs\n{full_response}```"
            else:
                msg = await self.get_playground_link(code)

            return msg
    
    async def get_playground_link(self, code):
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://discord.gg/9B7Dx79MgN",
        }

        data = json.dumps({"code": code})

        async with self.session.post(
            "https://play.rust-lang.org/meta/gist/", data=data, headers=headers
        ) as r:
            response = await r.json()

        return (
            "https://play.rust-lang.org/?version=nightly&mode=debug&edition=2018&gist="
            + response["id"]
        )

    async def cog_command_error(self, ctx: commands.Context, error):
        log.error("Playground error: %s", error)
        if isinstance(error, (discord.HTTPException, discord.Forbidden)):
            await ctx.send("Error while sending the output.")
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(CodeBlock.missing_error)
        if isinstance(error, commands.CommandError):
            await ctx.send(str(error))
'''
def setup(bot):
    bot.add_cog(Coding(bot))
