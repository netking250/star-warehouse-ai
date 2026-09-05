import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StarWarehouseLogo } from './StarWarehouseLogo'

describe('StarWarehouseLogo', () => {
  it('renders the full product identity by default', () => {
    render(<StarWarehouseLogo />)

    expect(screen.getByLabelText('星仓 AI 智能客服')).toBeInTheDocument()
    expect(screen.getByText('智能客服')).toBeInTheDocument()
  })

  it('hides the wordmark in compact mode', () => {
    render(<StarWarehouseLogo compact />)

    expect(screen.queryByText('智能客服')).not.toBeInTheDocument()
  })
})
