# 참고 자료

이 자료는 초기 기획 단계에서 2026-06-20에 확인했다.

## 증권사와 시장 데이터

- 한국투자증권 Open API 포털: https://apiportal.koreainvestment.com/
- 한국투자증권 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS API 가이드 페이지: https://apiportal.koreainvestment.com/apiservice-apiservice
- KRX 정보데이터시스템: https://data.krx.co.kr/
- OpenDART: https://opendart.fss.or.kr/
- FinanceDataReader: https://github.com/FinanceData/FinanceDataReader
- pykrx: https://github.com/sharebook-kr/pykrx
- pykrx PyPI: https://pypi.org/project/pykrx/
- yfinance: https://github.com/ranaroussi/yfinance

`pykrx`는 2026-06-20 기준 최신 1.2.8이 Python 3.13을 지원하는 것으로 확인했다. KRX/Naver 데이터를 스크래핑하므로 무분별한 호출을 피하고, 인증이 필요한 KRX 데이터는 사용자 확인 후 환경변수로 접근 권한을 설정한다.

## 플랫폼

- MySQL LTS와 Innovation 릴리스 모델: https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html
- Spring Boot 프로젝트 페이지: https://spring.io/projects/spring-boot/
- Spring Boot 시스템 요구사항: https://docs.spring.io/spring-boot/system-requirements.html
- SvelteKit 소개: https://svelte.dev/docs/kit/introduction
- Node.js 릴리스 일정: https://nodejs.org/en/about/previous-releases
- Python 버전 상태: https://devguide.python.org/versions/
- Oracle Java SE 지원 로드맵: https://www.oracle.com/java/technologies/java-se-support-roadmap.html
- Docker Desktop Mac 설치 가이드: https://docs.docker.com/desktop/setup/install/mac-install/
- MySQL Docker 공식 이미지: https://hub.docker.com/_/mysql

## UI 참고 후보

나중에 UI 방향을 검토할 때 볼 후보이며, 아직 결정 사항은 아니다.

- TradingView: https://www.tradingview.com/
- Finviz: https://finviz.com/
- Koyfin: https://www.koyfin.com/
- QuantConnect: https://www.quantconnect.com/
- Portfolio Visualizer: https://www.portfoliovisualizer.com/
- Naver Finance: https://finance.naver.com/

## 전략 참고 자료

- Jegadeesh/Titman 모멘텀 논문: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x
- Fama/French 팩터 논문: https://www.bauer.uh.edu/rsusmel/phd/Fama-French_JFE93.pdf
- Piotroski F-Score 논문 정보: https://www.gsb.stanford.edu/faculty-research/publications/value-investing-use-historical-financial-statement-information
- IBD CAN SLIM 소개: https://www.investors.com/ibd-videos/homestudy/1-introduction-to-can-slim/
- Donchian Channel 설명: https://www.investopedia.com/donchian-channels-formula-8415235
