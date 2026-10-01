class Executor:
    secure = False
    def shell(self, tree, command, seconds):
        (tree / 'mosslight/__init__.py').write_text(command)
        return {'exit_code':0, 'output':'ok'}
    def close(self):
        pass

def action(text):
    return {'tool':'shell','arguments':{'command':text}}
