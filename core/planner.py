"""Plan construction and dependency ordering."""
from core.contracts import Plan
class Planner:
    def build(self, plan): return plan
    def ordered(self, plan):
        items={x.id:x for x in plan.operations}; output=[]; visiting=set(); done=set()
        def visit(key):
            if key in visiting: raise ValueError('Dependency cycle detected')
            if key in done:return
            if key not in items: raise ValueError(f'Unknown dependency: {key}')
            visiting.add(key)
            for dep in items[key].dependencies: visit(dep)
            visiting.remove(key); done.add(key); output.append(items[key])
        for key in items: visit(key)
        return output
