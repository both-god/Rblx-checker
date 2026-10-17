class RepeatedSquaringSolver:
    __slots__ = ("n", "a", "t")

    def __init__(self, params: dict):
        self.n = int(params["N"])
        self.a = int(params["A"]) % self.n
        self.t = int(params["T"])

    def solve(self) -> str:
        result = self.a
        
        for _ in range(self.t):
            result = result * result % self.n

        return str(result)