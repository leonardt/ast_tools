__ALL__ = ['F', 'f', 'G', 'g', 'h']
class F: pass

def f(x):
    return x

@f
class G: pass

@f
def g(): pass

def h():
    local_var = 1
    def h_():
        pass
    return h_

