import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Message } from '@/types'
import { ChatInput } from './ChatInput'
import { ChatMessageList } from './ChatMessageList'
import { FeedbackWidget } from './FeedbackWidget'

describe('Customer conversation presentation', () => {
  it('gives send and stop generation distinct accessible actions', () => {
    const onSend = vi.fn()
    const onCancel = vi.fn()
    const { rerender } = render(
      <ChatInput
        value="查询订单"
        onChange={vi.fn()}
        onSend={onSend}
        onCancel={onCancel}
        isLoading={false}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(onSend).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: '添加附件' })).not.toBeInTheDocument()

    rerender(
      <ChatInput value="" onChange={vi.fn()} onSend={onSend} onCancel={onCancel} isLoading />
    )
    fireEvent.click(screen.getByRole('button', { name: '停止生成' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('keeps Enter send and Shift+Enter newline behavior', () => {
    const onSend = vi.fn()
    render(<ChatInput value="hello" onChange={vi.fn()} onSend={onSend} isLoading={false} />)

    const input = screen.getByRole('textbox', { name: '消息输入' })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })
    expect(onSend).toHaveBeenCalledOnce()
  })

  it('renders a truthful welcome state and sends the existing quick-task prompt', () => {
    const onQuickTask = vi.fn()
    const messages: Message[] = [
      {
        id: 'welcome',
        role: 'assistant',
        content: 'welcome',
        timestamp: new Date(),
      },
    ]
    render(<ChatMessageList messages={messages} isLoading={false} onQuickTask={onQuickTask} />)

    expect(screen.getByRole('heading', { name: '今天需要处理什么？' })).toBeInTheDocument()
    expect(screen.queryByText('安全响应')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /查询我的订单/ }))
    expect(onQuickTask).toHaveBeenCalledWith('帮我查询一下最近的订单状态')
  })

  it('keeps low-confidence feedback actionable without calling the answer wrong', () => {
    const onSubmit = vi.fn()
    render(
      <FeedbackWidget
        messageId="assistant-1"
        messageIndex={1}
        confidenceScore={0.45}
        autoTrigger
        onSubmit={onSubmit}
      />
    )

    expect(screen.getByText('此回复置信度较低，可帮助我们改进。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '点踩' }))
    fireEvent.click(screen.getByRole('button', { name: '准确性' }))
    fireEvent.change(screen.getByLabelText('详细说明（可选）'), {
      target: { value: '需要更清晰的办理条件' },
    })
    fireEvent.click(screen.getByRole('button', { name: '提交反馈' }))

    expect(onSubmit).toHaveBeenCalledWith(
      'assistant-1',
      'down',
      1,
      'accuracy',
      '需要更清晰的办理条件'
    )
  })
})
