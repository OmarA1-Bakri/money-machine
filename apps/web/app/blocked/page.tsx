import { OperatorViewPage, type OperatorPageProps } from "../../components/operator-view";

export const dynamic = "force-dynamic";

export default function Page(props: OperatorPageProps) {
  return <OperatorViewPage view="blocked" {...props} />;
}
