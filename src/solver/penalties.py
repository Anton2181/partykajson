
class SolverPenalties:
    def __init__(self, rule_names, ratio=10):
        """
        rule_names: list of strings describing the rules in order of importance (highest penalty first).
        ratio: n defined ratio (default 10).
        
        Start value is ratio^(n-1) where n is number of entries.
        """
        self.rule_names = rule_names
        self.ratio = ratio
        self.ladder = []
        
        n = len(rule_names)
        if n == 0:
            return

        # start_value = ratio^(n-1)
        # Example: 3 rules, ratio 10. 10^(2) = 100.
        # Ladder: [100, 10, 1]
        start_value = ratio ** (n - 1)
        
        current = start_value
        for _ in range(n):
            self.ladder.append(int(current))
            current = current / ratio
            
    def get_penalty(self, index):
        if index < 0 or index >= len(self.ladder):
            return 0
        return self.ladder[index]

    def get_rule_name(self, index):
        if index < 0 or index >= len(self.rule_names):
            return "Unknown"
        return self.rule_names[index]

    def get_penalty_by_name(self, name):
        try:
            index = self.rule_names.index(name)
            return self.get_penalty(index)
        except ValueError:
            return 0
