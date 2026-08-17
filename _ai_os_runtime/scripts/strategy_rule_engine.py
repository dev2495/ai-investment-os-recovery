#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Sequence


ENGINE_VERSION = "bounded_strategy_expression_v1"
SERIES_NAMES = {"open", "high", "low", "close", "volume"}
STATE_NAMES = {"holding_bars", "holding_days"}
FUNCTIONS = {"sma", "ema", "rsi", "atr", "vwap", "zscore", "crosses_above", "crosses_below"}
ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant, ast.And, ast.Or, ast.Not, ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)


@dataclass(frozen=True)
class CompiledRules:
    entry: str
    exit: str
    entry_tree: ast.Expression
    exit_tree: ast.Expression
    rule_hash: str


def _canonical(expression: str) -> str:
    return " ".join(expression.strip().split())


def _validate(tree: ast.Expression, label: str) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"{label} uses unsupported syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.lower() not in SERIES_NAMES | STATE_NAMES | FUNCTIONS:
            raise ValueError(f"{label} uses unsupported name: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id.lower() not in FUNCTIONS:
                raise ValueError(f"{label} uses an unsupported function")
            if node.keywords:
                raise ValueError(f"{label} function calls cannot use keyword arguments")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
            raise ValueError(f"{label} supports only numeric constants")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            if not isinstance(node.right, ast.Constant) or abs(float(node.right.value)) > 4:
                raise ValueError(f"{label} exponent must be a constant between -4 and 4")


def compile_rule_set(entry: str, exit_rule: str) -> CompiledRules:
    normalized_entry = _canonical(entry)
    normalized_exit = _canonical(exit_rule)
    if not normalized_entry or not normalized_exit:
        raise ValueError("both entry and exit expressions are required")
    try:
        entry_tree = ast.parse(normalized_entry, mode="eval")
        exit_tree = ast.parse(normalized_exit, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid strategy expression: {exc.msg}") from exc
    _validate(entry_tree, "entry")
    _validate(exit_tree, "exit")
    payload = {"engine": ENGINE_VERSION, "entry": normalized_entry, "exit": normalized_exit}
    rule_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return CompiledRules(normalized_entry, normalized_exit, entry_tree, exit_tree, rule_hash)


def _rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    output: list[float | None] = []
    running = 0.0
    for index, value in enumerate(values):
        running += float(value)
        if index >= window:
            running -= float(values[index - window])
        output.append(running / window if index + 1 >= window else None)
    return output


def _rolling_stdev(values: Sequence[float], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
            continue
        sample = [float(value) for value in values[index + 1 - window:index + 1]]
        mean = sum(sample) / window
        variance = sum((value - mean) ** 2 for value in sample) / window
        output.append(math.sqrt(variance))
    return output


class RuleEvaluator:
    def __init__(self, bars: Sequence[Any]):
        self.bars = bars
        self.series = {name: [float(getattr(bar, name)) for bar in bars] for name in SERIES_NAMES}
        self.cache: dict[str, list[float | bool | None]] = {}

    def _key(self, node: ast.AST) -> str:
        return ast.dump(node, annotate_fields=True, include_attributes=False)

    def series_for(self, node: ast.AST) -> list[float | bool | None]:
        key = self._key(node)
        if key in self.cache:
            return self.cache[key]
        if isinstance(node, ast.Name) and node.id.lower() in SERIES_NAMES:
            result: list[float | bool | None] = list(self.series[node.id.lower()])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            result = self._indicator(node.func.id.lower(), node.args)
        else:
            raise ValueError("indicator arguments must be a price/volume series or another indicator")
        self.cache[key] = result
        return result

    @staticmethod
    def _window(node: ast.AST, label: str) -> int:
        if not isinstance(node, ast.Constant) or not isinstance(node.value, (int, float)):
            raise ValueError(f"{label} window must be a numeric constant")
        window = int(node.value)
        if window < 2 or window > 1000:
            raise ValueError(f"{label} window must be between 2 and 1000")
        return window

    def _indicator(self, name: str, args: Sequence[ast.AST]) -> list[float | bool | None]:
        count = len(self.bars)
        if name in {"sma", "ema", "rsi", "zscore"}:
            if len(args) != 2:
                raise ValueError(f"{name} requires a series and window")
            source = self.series_for(args[0])
            values = [float(value) if value is not None else math.nan for value in source]
            window = self._window(args[1], name)
            if name == "sma":
                return _rolling_mean(values, window)
            if name == "ema":
                alpha = 2.0 / (window + 1.0)
                output: list[float | None] = []
                current: float | None = None
                for value in values:
                    current = value if current is None else alpha * value + (1 - alpha) * current
                    output.append(current)
                return output
            if name == "zscore":
                means = _rolling_mean(values, window)
                stdevs = _rolling_stdev(values, window)
                return [
                    (values[index] - float(means[index])) / float(stdevs[index])
                    if means[index] is not None and stdevs[index] not in {None, 0.0} else None
                    for index in range(count)
                ]
            deltas = [0.0] + [values[index] - values[index - 1] for index in range(1, count)]
            gains = _rolling_mean([max(value, 0.0) for value in deltas], window)
            losses = _rolling_mean([max(-value, 0.0) for value in deltas], window)
            return [
                100.0 if gains[index] is not None and losses[index] == 0 else
                100.0 - 100.0 / (1.0 + float(gains[index]) / float(losses[index]))
                if gains[index] is not None and losses[index] not in {None, 0.0} else None
                for index in range(count)
            ]
        if name == "atr":
            if len(args) != 1:
                raise ValueError("atr requires a window")
            window = self._window(args[0], name)
            highs, lows, closes = self.series["high"], self.series["low"], self.series["close"]
            true_ranges = [highs[0] - lows[0]] if count else []
            true_ranges.extend(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, count))
            return _rolling_mean(true_ranges, window)
        if name == "vwap":
            if args:
                raise ValueError("vwap takes no arguments")
            cumulative_pv = 0.0
            cumulative_volume = 0.0
            output: list[float | None] = []
            for index in range(count):
                typical = (self.series["high"][index] + self.series["low"][index] + self.series["close"][index]) / 3.0
                volume = self.series["volume"][index]
                cumulative_pv += typical * volume
                cumulative_volume += volume
                output.append(cumulative_pv / cumulative_volume if cumulative_volume else None)
            return output
        if name in {"crosses_above", "crosses_below"}:
            if len(args) != 2:
                raise ValueError(f"{name} requires two series")
            left = self.series_for(args[0])
            right = self.series_for(args[1])
            output: list[bool] = [False]
            for index in range(1, count):
                values = (left[index - 1], right[index - 1], left[index], right[index])
                if any(value is None for value in values):
                    output.append(False)
                elif name == "crosses_above":
                    output.append(float(left[index - 1]) <= float(right[index - 1]) and float(left[index]) > float(right[index]))
                else:
                    output.append(float(left[index - 1]) >= float(right[index - 1]) and float(left[index]) < float(right[index]))
            return output
        raise ValueError(f"unsupported indicator: {name}")

    def value(self, node: ast.AST, index: int, holding_bars: int) -> float | bool | None:
        if isinstance(node, ast.Expression):
            return self.value(node.body, index, holding_bars)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            name = node.id.lower()
            if name in SERIES_NAMES:
                return self.series[name][index]
            if name in STATE_NAMES:
                return holding_bars
        if isinstance(node, ast.Call):
            return self.series_for(node)[index]
        if isinstance(node, ast.UnaryOp):
            value = self.value(node.operand, index, holding_bars)
            if isinstance(node.op, ast.Not): return not bool(value)
            if isinstance(node.op, ast.USub): return -float(value)
            if isinstance(node.op, ast.UAdd): return float(value)
        if isinstance(node, ast.BoolOp):
            values = [bool(self.value(value, index, holding_bars)) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.BinOp):
            left = self.value(node.left, index, holding_bars)
            right = self.value(node.right, index, holding_bars)
            if left is None or right is None: return None
            a, b = float(left), float(right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b if b else None
            if isinstance(node.op, ast.Mod): return a % b if b else None
            if isinstance(node.op, ast.Pow): return a ** b
        if isinstance(node, ast.Compare):
            left = self.value(node.left, index, holding_bars)
            if left is None: return False
            for operator, comparator in zip(node.ops, node.comparators):
                right = self.value(comparator, index, holding_bars)
                if right is None: return False
                if isinstance(operator, ast.Lt): ok = float(left) < float(right)
                elif isinstance(operator, ast.LtE): ok = float(left) <= float(right)
                elif isinstance(operator, ast.Gt): ok = float(left) > float(right)
                elif isinstance(operator, ast.GtE): ok = float(left) >= float(right)
                elif isinstance(operator, ast.Eq): ok = left == right
                else: ok = left != right
                if not ok: return False
                left = right
            return True
        raise ValueError(f"unsupported expression node: {type(node).__name__}")


def positions_for_rule_set(bars: Sequence[Any], rules: CompiledRules) -> list[int]:
    evaluator = RuleEvaluator(bars)
    positions: list[int] = []
    position = 0
    holding_bars = 0
    for index in range(len(bars)):
        if position:
            holding_bars += 1
            if bool(evaluator.value(rules.exit_tree, index, holding_bars)):
                position = 0
                holding_bars = 0
        elif bool(evaluator.value(rules.entry_tree, index, 0)):
            position = 1
            holding_bars = 0
        positions.append(position)
    return positions
