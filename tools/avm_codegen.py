"""Small build-time compiler for the restricted Python-shaped AVM1 helpers.

Only explicit statements below are accepted. No Python code is evaluated.
"""
import ast
import struct


class Compiler:
    def __init__(self, Asm, undef):
        self.Asm, self.undef = Asm, undef
        self.seq = 0
        self.loops = []

    def label(self):
        self.seq += 1
        return 'c%d' % self.seq

    def expression(self, a, n):
        if isinstance(n, ast.Constant):
            a.push(self.undef if n.value is None else n.value)
        elif isinstance(n, ast.Name):
            a.var(n.id)
        elif isinstance(n, ast.Attribute):
            self.expression(a, n.value); a.member(n.attr)
        elif isinstance(n, ast.Subscript):
            self.expression(a, n.value); self.expression(a, n.slice); a.op('getmember')
        elif isinstance(n, ast.List):
            for v in reversed(n.elts): self.expression(a, v)
            a.push(len(n.elts)).op('initarray')
        elif isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                self.expression(a, k); self.expression(a, v)
            a.push(len(n.keys)).op('initobject')
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            self.expression(a, n.operand); a.op('not')
        elif isinstance(n, ast.BinOp):
            self.expression(a, n.left); self.expression(a, n.right)
            a.op({ast.Add:'add2',ast.Sub:'subtract',ast.Mult:'multiply',ast.Div:'divide',ast.Mod:'modulo'}[type(n.op)])
        elif isinstance(n, ast.BoolOp):
            end = self.label()
            for value in n.values[:-1]:
                self.expression(a, value); a.parts.append(b'\x4c')  # Duplicate.
                if isinstance(n.op, ast.And): a.op('not')
                a.iftrue(end).op('pop')
            self.expression(a, n.values[-1]); a.label(end)
        elif isinstance(n, ast.Compare) and len(n.ops)==1:
            left, right, op = n.left,n.comparators[0],n.ops[0]
            if isinstance(op,(ast.Gt,ast.LtE)): left,right=right,left
            self.expression(a,left);self.expression(a,right)
            a.op('equals2' if isinstance(op,(ast.Eq,ast.NotEq,ast.Is,ast.IsNot)) else 'less2')
            if isinstance(op,(ast.NotEq,ast.IsNot,ast.LtE,ast.GtE)):a.op('not')
        elif isinstance(n, ast.Call):
            if isinstance(n.func,ast.Name) and n.func.id=='len':
                self.expression(a,n.args[0]);a.member('length');return
            if isinstance(n.func,ast.Name) and n.func.id=='kind':
                self.expression(a,n.args[0]);a.parts.append(b'\x44');return
            if isinstance(n.func,ast.Name) and n.func.id=='new':
                for v in reversed(n.args[1:]):self.expression(a,v)
                constructor = n.args[0]
                a.push(len(n.args)-1)
                if isinstance(constructor, ast.Attribute):
                    self.expression(a, constructor.value)
                    a.push(constructor.attr).op('newmethod')
                else:
                    if isinstance(constructor, ast.Name):
                        a.push(constructor.id)
                    else:
                        self.expression(a, constructor)
                    a.op('newobject')
                return
            for v in reversed(n.args): self.expression(a,v)
            a.push(len(n.args))
            if isinstance(n.func,ast.Attribute):
                self.expression(a,n.func.value);a.push(n.func.attr).op('callmethod')
            else:
                a.push(n.func.id).op('callfunc')
        else:
            raise ValueError('unsupported AVM expression: '+ast.dump(n))

    def statements(self,a,body):
        for n in body:
            if isinstance(n,ast.Assign):
                assert len(n.targets)==1
                t=n.targets[0]
                if isinstance(t,ast.Name):
                    a.push(t.id);self.expression(a,n.value);a.op('definelocal')
                else:
                    self.expression(a,t.value)
                    if isinstance(t,ast.Attribute):a.push(t.attr)
                    else:self.expression(a,t.slice)
                    self.expression(a,n.value);a.op('setmember')
            elif isinstance(n,ast.Expr):self.expression(a,n.value);a.op('pop')
            elif isinstance(n,ast.Return):
                self.expression(a,n.value or ast.Constant(None));a.op('return')
            elif isinstance(n,ast.If):
                other,end=self.label(),self.label()
                self.expression(a,n.test);a.op('not').iftrue(other)
                self.statements(a,n.body);a.push(True).iftrue(end).label(other)
                self.statements(a,n.orelse);a.label(end)
            elif isinstance(n,ast.While):
                start,end=self.label(),self.label();a.label(start)
                self.expression(a,n.test);a.op('not').iftrue(end)
                self.loops.append((start,end));self.statements(a,n.body);self.loops.pop()
                a.push(True).iftrue(start).label(end)
            elif isinstance(n,ast.Break):a.push(True).iftrue(self.loops[-1][1])
            elif isinstance(n,ast.Continue):a.push(True).iftrue(self.loops[-1][0])
            else:raise ValueError('unsupported AVM statement: '+ast.dump(n))
        return a

    def functions(self, source):
        out=[]
        for n in ast.parse(source).body:
            assert isinstance(n,ast.FunctionDef)
            a=self.statements(self.Asm(),n.body)
            out.append((n.name,tuple(arg.arg for arg in n.args.args),a))
        return out


def protected_call(Asm, function, params, undef):
    """Catch storage/format errors without swallowing native chat handlers."""
    a=Asm()
    for p in reversed(params):a.var(p)
    a.push(len(params)).var('_global').push(function).op('callmethod').op('pop')
    body=a.assemble()
    # ActionTry: catch into local name; no finally and no register binding.
    data=bytes((1,))+struct.pack('<HHH',len(body),0,0)+b'cacheError\0'+body
    out=Asm();out.parts.append(b'\x8f'+struct.pack('<H',len(data)-len(body))+data)
    return out
