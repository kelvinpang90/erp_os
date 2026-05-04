import { theme, type ThemeConfig } from 'antd'

export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#1677ff',
    borderRadius: 6,
    wireframe: false,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: {
      headerBg: '#141414',
      siderBg: '#1f1f1f',
      bodyBg: '#000000',
    },
    Card: {
      borderRadiusLG: 8,
      colorBgContainer: '#1f1f1f',
    },
    Table: {
      headerBg: '#262626',
    },
  },
}
