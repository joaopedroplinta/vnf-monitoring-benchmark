%%
%% ifpr-pinhais.cls
%% Classe LaTeX para Trabalhos Acadêmicos do IFPR - Campus Pinhais
%% Baseada na estrutura da classe utfpr-pg e adaptada ao modelo do IFPR Pinhais
%% (APÊNDICE K – Modelo de Trabalho Acadêmico para Projeto de Curso I)
%%
%% Compatível com abntex2
%%

\NeedsTeXFormat{LaTeX2e}[1999/12/01]
\ProvidesClass{ifpr-pinhais}
[2026/04/15 v1.0.0 Classe para trabalhos acadêmicos do IFPR Campus Pinhais]

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{abntex2}}
\ProcessOptions\relax

\LoadClass[
  a4paper,
  12pt,
  openright,
  oneside,
  chapter=TITLE,
  section=TITLE,
  hidelinks,
  brazil
]{abntex2}

%% ---- Pacotes requeridos ----
\RequirePackage[alf,
  abnt-emphasize=bf,
  abnt-repeated-author-omit=yes,
  abnt-etal-text=it]{abntex2cite}
\RequirePackage{indentfirst}
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage{lastpage}
\RequirePackage{etoolbox}
\RequirePackage{graphicx}
\RequirePackage{geometry}
\RequirePackage{tgtermes}
\RequirePackage[font=small,labelfont=bf]{caption}
\RequirePackage{hyperref}
\RequirePackage{lipsum}

%% ---- Margens ABNT ----
\setlrmarginsandblock{3cm}{2cm}{*}
\setulmarginsandblock{3cm}{2cm}{*}
\checkandfixthelayout

%% ---- Identificação da instituição ----
\newcommand{\ifpr}{Instituto Federal do Paran\'{a}}
\newcommand{\campus}{Campus Pinhais}

%% ---- Comandos de metadados ----
\newcommand*\erro[1]{\@latex@error{Defina \noexpand#1 no preâmbulo!}\@ehc}

\providecommand\imprimircurso{\erro\curso}
\newcommand*\curso[1]{\renewcommand{\imprimircurso}{#1}}

\providecommand\imprimirdepartamento{}
\newcommand*\departamento[1]{\renewcommand{\imprimirdepartamento}{#1}}

%% ---- CAPA ----
\renewcommand{\imprimircapa}{%
  \begin{capa}
    \begin{minipage}[c]{0.15\textwidth}
      \includegraphics[width=4cm]{logo-ifpr}
    \end{minipage}%
    \hfill
    \begin{minipage}[c]{0.15\textwidth}
      \raggedleft
      \includegraphics[width=2cm]{logo-mec}
    \end{minipage}

    \vspace{0.5cm}
    \center

    {\large\bfseries\MakeUppercase\ifpr}\par
    \vspace{0.3cm}
    {\large\bfseries\MakeUppercase\imprimirautor}\par

    \vfill

    {\large\bfseries\MakeUppercase\imprimirtitulo}\par

    \vfill

    {\large\MakeUppercase\imprimirlocal}\par
    {\large\imprimirdata}\par
  \end{capa}
}

%% ---- FOLHA DE ROSTO ----
\renewcommand{\folhaderostocontent}{%
  \begin{center}

    \vspace*{1cm}

    {\large\MakeUppercase\imprimirautor}

    \vspace*{\fill}

    {\large\bfseries\MakeUppercase\imprimirtitulo}\par

    \vspace*{\fill}

    \abntex@ifnotempty{\imprimirpreambulo}{%
      \hspace{.45\textwidth}
      \begin{minipage}{.5\textwidth}
        \SingleSpacing
        \imprimirpreambulo
      \end{minipage}%
      \vspace*{\fill}
    }%

    {\large\imprimirorientadorRotulo~\imprimirorientador\par}
    \abntex@ifnotempty{\imprimircoorientador}{%
      {\large\imprimircoorientadorRotulo~\imprimircoorientador}%
    }%

    \vspace*{\fill}

    {\large\MakeUppercase\imprimirlocal}\par
    {\large\imprimirdata}

    \vspace*{1cm}
  \end{center}
}

%% ---- FOLHA DE APROVAÇÃO ----
\newcommand{\imprimirfolhadeaprovacao}{%
  \begin{folhadeaprovacao}
    \begin{center}
      {\bfseries FOLHA DE APROVAÇÃO}

      \vspace{1.5cm}
      {\large\imprimirautor}

      \vspace{1cm}
      {\large\bfseries\MakeUppercase\imprimirtitulo}

      \vspace{1cm}
      \begin{SingleSpace}
        O presente trabalho foi avaliado e aprovado por banca examinadora composta pelos seguintes membros:
      \end{SingleSpace}
    \end{center}

    \vspace{2cm}
    \begin{center}
      \assinatura{\textbf{Prof. Componente de Banca 1}\\Instituição a que pertence}
      \assinatura{\textbf{Prof. Componente de Banca 2}\\Instituição a que pertence}
      \assinatura{\textbf{Prof. Orientador}\\Guilherme Werneck de Oliveira}
    \end{center}

    \begin{center}
      \vspace{1cm}
      {\imprimirlocal, \imprimirdata}
    \end{center}
  \end{folhadeaprovacao}
}

%% ---- Tipografia ----
\renewcommand{\ABNTEXchapterfont}{\bfseries}
\renewcommand{\ABNTEXchapterfontsize}{\normalsize}
\renewcommand{\ABNTEXsectionfont}{}
\renewcommand{\ABNTEXsectionfontsize}{\normalsize}
\renewcommand{\ABNTEXsubsectionfontsize}{\normalsize}
\renewcommand{\ABNTEXsubsubsubsectionfont}{\itshape}

%% ---- Espaçamentos ----
\pretocmd{\pretextual}{\SingleSpacing}{}{}
\pretocmd{\textual}{\pagestyle{simple}\OnehalfSpacing}{}{}

\setlength\beforechapskip{2.0\onelineskip}
\setlength\afterchapskip{2.0\onelineskip}
\setlength\beforesecskip{\beforechapskip}
\setlength\aftersecskip{\afterchapskip}
\setlength\beforesubsecskip{\beforechapskip}
\setlength\aftersubsecskip{\afterchapskip}
\setlength\beforesubsubsecskip{\beforechapskip}
\setlength\aftersubsubsecskip{\afterchapskip}
\setlength\parindent{1.5cm}

%% ---- Sumário ----
\renewcommand\numberlinehook[1]{%
  \addtolength{\@tempdima}{\widthof{#1}}
}
\renewcommand\chapternumberlinehook\numberlinehook
\renewcommand{\tocprintchapter}{%
  \addtocontents{toc}{\cftsetindents{chapter}{0em}{1em}}}
\cftsetindents{section}{0em}{1em}
\cftsetindents{subsection}{0em}{1em}
\cftsetindents{subsubsection}{0em}{1em}
\cftsetindents{paragraph}{0em}{1em}
\setlength\cftbeforechapterskip{0cm}
\renewcommand{\cftchapterleader}{\normalfont\cftdotfill{\cftchapterdotsep}}
\renewcommand{\cftdotsep}{1}

\newcommand{\upcase}[1]{\uppercase{#1}}
\renewcommand{\cftchapterfont}{\normalfont\bfseries}
\renewcommand{\cftsectionfont}{\mdseries\upcase}
\renewcommand{\cftsubsectionfont}{\normalfont}
\renewcommand{\cftsubsubsectionfont}{\normalfont}
\renewcommand{\cftparagraphfont}{\normalfont\itshape}
\renewcommand{\cftchapterpagefont}{\cftchapterfont}
\renewcommand{\cftsectionpagefont}{\cftsectionfont}
\renewcommand{\cftsubsectionpagefont}{\cftsubsectionfont}
\renewcommand{\cftsubsubsectionpagefont}{\cftsubsubsectionfont}
\renewcommand{\cftparagraphpagefont}{\cftparagraphfont}

%% ---- Referências ----
\renewcommand{\bibsection}{\chapter*{\bibname}\prebibhook}

%% ---- Quadros (elemento flutuante adicional) ----
\RequirePackage[within=none]{newfloat}
\DeclareFloatingEnvironment[
  fileext=loq,
  listname=Lista de Quadros,
  name=Quadro,
  placement=tbhp,
]{quadro}

%% End of file `ifpr-pinhais.cls'
