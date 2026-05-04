import { Grid, Modal, type ModalProps } from 'antd'

// Wrapper around antd Modal that goes full-screen on xs/sm and stays normal on md+.
// Use this for any business modal where the form/content has more than a couple of fields.
export default function ResponsiveModal(props: ModalProps) {
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md

  if (isMobile) {
    return (
      <Modal
        {...props}
        width="100vw"
        style={{ top: 0, paddingBottom: 0, maxWidth: '100vw', ...props.style }}
        styles={{
          body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto', ...(props.styles?.body ?? {}) },
          ...props.styles,
        }}
      />
    )
  }

  return <Modal {...props} />
}
