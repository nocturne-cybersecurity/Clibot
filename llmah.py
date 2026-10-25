"""LLMAH command-line entry point."""
import argparse, sys
from core.assistant import Assistant
from interface.terminal import Terminal
from interface.formatter import format_response
from intelligence.ollama_setup import check_and_prompt
VERSION='0.2.0'
def main(argv=None):
    parser=argparse.ArgumentParser(prog='llmah',description='Asistente local offline para diagnóstico y administración Linux')
    parser.add_argument('-V','--version',action='version',version=f'%(prog)s {VERSION}')
    parser.add_argument('-c','--command',help='Ejecuta una solicitud y termina')
    parser.add_argument('request',nargs='*',help='Solicitud en lenguaje natural (también admite varias palabras sin comillas)')
    args=parser.parse_args(argv)
    try:
        # Check for LLM setup on first run
        check_and_prompt()
        assistant=Assistant()
        if args.command and args.request:
            parser.error('usa --command o una solicitud posicional, no ambas')
        request=args.command or ' '.join(args.request)
        if request:
            response=assistant.handle(request); print(format_response(response))
            if response.get('clarification') or response.get('error'):return 2
            return 0 if all(r.success for r in response.get('results',[])) else 1
        Terminal(assistant).run(); return 0
    except KeyboardInterrupt:return 130
    except Exception as exc:
        print(f'Error de inicialización: {exc}',file=sys.stderr); return 1
if __name__=='__main__':raise SystemExit(main())
