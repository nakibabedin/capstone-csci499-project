export default function AboutPage() {
 
  const features = [
    {
      number: 1,
      title: "Blood Test PDF Upload and Parsing",
      description:
        "Upload a blood test report and we organize and display biomarker names, measured values, units, reference ranges, and more.",
    },
    {
      number: 2,
      title: "Graphs and Data Visualization",
      description:
        "View your personalized graphs on your blood test results to visually identify trends and changes.",
    },
    {
      number: 3,
      title: "Learn",
      description:
        "Get more insightful informataion about your blood test results and learn more about your next steps.",
    },
  ];
  
  return (
    <div className="pb-20 pt-8 sm:pb-28 sm:pt-12">
      <section className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
        <div className="max-w-lg">
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-teal-700">
            About us
          </p>
          <h1 className="text-4xl font-semibold leading-tight text-slate-900 sm:text-5xl">
            Making health information easier to understand.
          </h1>
          <p className="mt-6 text-base leading-7 text-slate-700">
            We’re building a clearer way to understand blood test lab information. Our goal is to
            make complex results feel more approachable and give people a thoughtful place to
            learn what they mean.
          </p>
          <p className="mt-4 text-base leading-7 text-slate-600">
            Good information starts with curiosity. We’re bringing useful tools and reliable
            context together to help people feel more informed as they navigate their health.
          </p>
        </div>

        <img
          alt="A laboratory scientist examining a sample through a microscope"
          className="aspect-[16/10] w-full rounded-lg object-cover"
          src="/shutterstock_504794353.jpg"
        />
      </section>

      <section aria-labelledby="features-heading" className="mt-24 sm:mt-32">
        <div className="max-w-xl">
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-teal-700">
            What we’re building
          </p>
          <h2 className="text-3xl font-semibold text-slate-900" id="features-heading">
            Features
          </h2>
          <p className="mt-3 text-base leading-7 text-slate-600">
            We’re shaping a set of features to make health information more useful and accessible.
            More details will be shared as the project grows.
          </p>
        </div>

        <div className="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-3">
          {features.map((features) => (
            <div className="border-t border-slate-300 pt-5" key={features.number}>
              <p className="text-sm font-semibold text-teal-700">
                {features.title}
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {features.description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
