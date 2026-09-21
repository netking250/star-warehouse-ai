import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

type Oklch = readonly [lightness: number, chroma: number, hue: number]

function readTokens(block: string): Record<string, Oklch> {
  return Object.fromEntries(
    Array.from(block.matchAll(/--([a-z-]+):\s*([\d.]+)\s+([\d.]+)\s+([\d.]+);/g)).map(
      ([, name, lightness, chroma, hue]) => [
        name,
        [Number(lightness), Number(chroma), Number(hue)] as Oklch,
      ]
    )
  )
}

function linearSrgb([lightness, chroma, hue]: Oklch): readonly [number, number, number] {
  const radians = (hue * Math.PI) / 180
  const a = chroma * Math.cos(radians)
  const b = chroma * Math.sin(radians)
  const lPrime = lightness + 0.3963377774 * a + 0.2158037573 * b
  const mPrime = lightness - 0.1055613458 * a - 0.0638541728 * b
  const sPrime = lightness - 0.0894841775 * a - 1.291485548 * b
  const l = lPrime ** 3
  const m = mPrime ** 3
  const s = sPrime ** 3
  const clamp = (value: number): number => Math.min(1, Math.max(0, value))
  return [
    clamp(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    clamp(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    clamp(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ]
}

function relativeLuminance(color: Oklch): number {
  const [red, green, blue] = linearSrgb(color)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrast(first: Oklch, second: Oklch): number {
  const lighter = Math.max(relativeLuminance(first), relativeLuminance(second))
  const darker = Math.min(relativeLuminance(first), relativeLuminance(second))
  return (lighter + 0.05) / (darker + 0.05)
}

describe('theme contrast tokens', () => {
  it('keeps critical text and status combinations at WCAG AA contrast', () => {
    const css = readFileSync(path.resolve(process.cwd(), 'src/globals.css'), 'utf8')
    const lightBlock = css.match(/:root\s*{([\s\S]*?)}\s*\.dark\s*{/)?.[1]
    const darkBlock = css.match(/\.dark\s*{([\s\S]*?)}\s*\*/)?.[1]
    expect(lightBlock).toBeDefined()
    expect(darkBlock).toBeDefined()

    for (const [theme, tokens] of [
      ['light', readTokens(lightBlock ?? '')],
      ['dark', readTokens(darkBlock ?? '')],
    ] as const) {
      const pairs = [
        ['foreground', 'background'],
        ['muted-foreground', 'background'],
        ['primary-foreground', 'primary'],
        ['success', 'background'],
        ['success-foreground', 'success'],
        ['warning', 'background'],
        ['warning-foreground', 'warning'],
        ['danger', 'background'],
        ['danger-foreground', 'danger'],
        ['info', 'background'],
        ['info-foreground', 'info'],
      ] as const

      for (const [foreground, background] of pairs) {
        expect(
          contrast(tokens[foreground], tokens[background]),
          `${theme} ${foreground} on ${background}`
        ).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})
