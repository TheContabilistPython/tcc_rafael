#!/usr/bin/env python3
"""
Run the frontend with a single python command.

Behavior:
- If Node/npm are available and package.json exists, runs `npm start` in the frontend folder.
- Otherwise serves the `frontend/static` folder using Python's http.server on the chosen port.

Usage:
  python run_frontend.py        # auto-detect (node preferred)
  python run_frontend.py --no-node   # force python static server
  python run_frontend.py --use-node  # force npm start (will error if node not installed)

"""
import argparse
import os
import shutil
import subprocess
import sys
import http.server
import socketserver
import webbrowser


def serve_static(port, directory):
    if not os.path.isdir(directory):
        print(f"Erro: diretório estático não encontrado: {directory}")
        sys.exit(1)
    os.chdir(directory)
    # allow serving a favicon from the repository root (one level up)
    favicon_path = os.path.abspath(os.path.join(directory, '..', 'favicon.ico'))

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/favicon.ico' and os.path.exists(favicon_path):
                try:
                    with open(favicon_path, 'rb') as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'image/x-icon')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    self.send_error(404)
                return
            return super().do_GET()

    handler = CustomHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"Servindo arquivos estáticos em {url} (ctrl-c para parar)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nServidor interrompido pelo usuário')


def run_npm_start(frontend_dir):
    print("Iniciando frontend com 'npm start'...")
    try:
        proc = subprocess.run(['npm', 'start'], cwd=frontend_dir)
        if proc.returncode != 0:
            print(f"npm retornou código {proc.returncode}")
            return False
        return True
    except FileNotFoundError:
        print("npm não encontrado no PATH")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-p', type=int, default=3000, help='Porta para servir o frontend com http.server (default 3000)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--use-node', action='store_true', help='Forçar uso do Node/npm')
    group.add_argument('--no-node', action='store_true', help='Não usar Node, forçar python static server')
    args = parser.parse_args()

    # determine directories
    this_file = os.path.abspath(__file__)
    frontend_dir = os.path.dirname(this_file)
    static_dir = os.path.join(frontend_dir, 'static')

    has_node = shutil.which('node') is not None and shutil.which('npm') is not None
    has_package = os.path.exists(os.path.join(frontend_dir, 'package.json'))

    if args.use_node:
        if not has_node:
            print('Erro: opção --use-node especificada, porém node/npm não encontrados.')
            sys.exit(1)
        if not has_package:
            print('Erro: package.json não encontrado na pasta frontend; não é possível rodar npm start')
            sys.exit(1)
        run_npm_start(frontend_dir)
        return

    if args.no_node:
        serve_static(args.port, static_dir)
        return

    # auto-detect: prefer node if available and package.json exists
    if has_node and has_package:
        ok = run_npm_start(frontend_dir)
        if ok:
            return
        print('Fallback: não foi possível iniciar via npm; iniciando servidor estático Python')

    # fallback: python static server
    serve_static(args.port, static_dir)


if __name__ == '__main__':
    main()
