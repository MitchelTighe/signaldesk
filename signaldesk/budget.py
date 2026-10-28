"""Pre-request reservations. Failed/unknown requests never refund the run budget."""
from dataclasses import dataclass
from decimal import Decimal, DecimalException
import json
from pathlib import Path


class GuardError(Exception):
    """Safe to log: no remote content or request headers."""


PRICING = json.loads(Path(__file__).with_name('pricing.json').read_text())
MODELS = tuple(PRICING['models'])
LIGHTNING = 'nvidia/Nemotron-3_5-Lightning'
SUPER = 'nvidia/nemotron-3-super-120b-a12b'
VISION = 'nvidia/Nemotron-3.5-Super-VL'


@dataclass
class Budget:
    max_calls: int = 80
    max_tokens: int = 1_500_000
    max_usd: Decimal = Decimal('1')
    multiplier: Decimal = Decimal('2')
    calls: int = 0
    reserved_tokens: int = 0
    reserved_usd: Decimal = Decimal('0')
    observed_tokens: int = 0
    observed_usd: Decimal = Decimal('0')
    search_calls: int = 0
    search_credits_observed: int = 0

    def __post_init__(self):
        try:
            self.max_usd = Decimal(str(self.max_usd))
            self.multiplier = Decimal(str(self.multiplier))
        except DecimalException:
            raise GuardError('Invalid decimal budget limit') from None
        if (type(self.max_calls) is not int or not 1 <= self.max_calls <= 100
                or type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 2_000_000
                or not self.max_usd.is_finite() or not 0 < self.max_usd <= 1
                or not self.multiplier.is_finite() or not 2 <= self.multiplier <= 100):
            raise GuardError('Invalid limits: at most 100 calls, 2000000 tokens, USD 1; price multiplier >= 2')

    def _reserve(self, tokens, dollars, search=False):
        if self.calls + 1 > self.max_calls:
            raise GuardError('Call cap would be exceeded; aborted before request')
        if self.reserved_tokens + tokens > self.max_tokens:
            raise GuardError('Token cap would be exceeded; aborted before request')
        if self.reserved_usd + dollars > self.max_usd:
            raise GuardError('Estimated USD cap would be exceeded; aborted before request')
        self.calls += 1
        self.search_calls += int(search)
        self.reserved_tokens += tokens
        self.reserved_usd += dollars

    def reserve(self, model, prompt_bound, output_cap):
        if model not in MODELS or type(prompt_bound) is not int or prompt_bound <= 0:
            raise GuardError('Unknown model or invalid input token bound')
        if type(output_cap) is not int or not 256 <= output_cap <= 2048:
            raise GuardError('Output cap must be an integer from 256 to 2048 tokens')
        rates = PRICING['models'][model]
        dollars = (Decimal(str(rates['input'])) * prompt_bound
                   + Decimal(str(rates['output'])) * output_cap) / 1_000_000
        self._reserve(prompt_bound + output_cap, dollars * self.multiplier)
        return prompt_bound, output_cap

    def reserve_search(self):
        # Basic search: one credit. USD .02 is an intentionally high planning bound,
        # not a quote or permission to incur a charge. Same global call/$ caps.
        self._reserve(0, Decimal('.02'), search=True)

    def observe(self, model, usage, reservation):
        if not isinstance(usage, dict):
            raise GuardError('Missing usage; retain reservation and stop')
        inp, out = usage.get('prompt_tokens'), usage.get('completion_tokens')
        total = usage.get('total_tokens')
        if (type(inp) is not int or type(out) is not int or type(total) is not int
                or min(inp, out) < 0 or total != inp + out):
            raise GuardError('Invalid usage; retain reservation and stop')
        self.observed_tokens += total
        rates = PRICING['models'][model]
        self.observed_usd += (Decimal(str(rates['input'])) * inp
                              + Decimal(str(rates['output'])) * out) / 1_000_000
        if inp > reservation[0] or out > reservation[1]:
            raise GuardError('Provider usage exceeded reservation; stop all further requests')
        return {'prompt_tokens': inp, 'completion_tokens': out, 'total_tokens': total}

    def summary(self):
        return {'max_calls': self.max_calls, 'max_tokens': self.max_tokens,
                'max_usd': float(self.max_usd), 'price_multiplier': float(self.multiplier),
                'calls_reserved': self.calls, 'search_calls': self.search_calls,
                'tavily_credits_observed': self.search_credits_observed,
                'tokens_reserved': self.reserved_tokens, 'usd_reserved_upper_estimate': float(self.reserved_usd),
                'tokens_observed': self.observed_tokens, 'usd_observed_estimate': float(self.observed_usd),
                'pricing_observed_at': PRICING['observed_at'],
                'note': 'Estimates, not an invoice. Reservations include failures; cached replay costs zero. '
                        'Observed USD estimate covers model token usage; Tavily is reported separately in credits. '
                        'Input bound is UTF-8 bytes plus 4096 framing tokens; vision adds 32768. '
                        'Rates must be rechecked before authorized use; usage overrun stops further calls.'}
