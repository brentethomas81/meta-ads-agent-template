import "./globals.css";

export const metadata = {
  title: "Meta Ads Agent — Dashboard",
  description: "Multi-brand Meta Ads performance, CAC traffic lights",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
