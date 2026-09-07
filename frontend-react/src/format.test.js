import { describe, expect, test } from 'vitest'
import { compactMoney, signedMoney, signedMillions, pct1, dec3, ms, score, FORMATTERS } from './format.js'

describe('format', () => {
  test('compactMoney', () => {
    expect(compactMoney(55123)).toBe('$55.1K'); expect(compactMoney(-1547526)).toBe('-$1.55M'); expect(compactMoney(914)).toBe('$914')
  })
  test('signedMoney keeps the sign', () => { expect(signedMoney(28600)).toBe('+$28.6K'); expect(signedMoney(-3300)).toBe('-$3.3K') })
  test('signedMillions formats millions with sign', () => {
    expect(signedMillions(1.5)).toBe('+$1.50M')
    expect(signedMillions(0)).toBe('$0')
    expect(signedMillions(-0.0033)).toBe('-$3.3K')
  })
  test('small formatters', () => { expect(pct1(28.83)).toBe('28.8%'); expect(dec3(0.5847)).toBe('0.585'); expect(ms(25.4)).toBe('25 ms'); expect(score(51.7)).toBe('52') })
  test('FORMATTERS map exposes every name', () => { expect(Object.keys(FORMATTERS).sort()).toEqual(['dec1','dec3','int','money','moneyS','ms','pct1','score','usd2']) })
})
