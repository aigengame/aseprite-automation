# Test standards

Read this document before you write or change a test.

A test is evidence for one claim. The six principles below tell when a test gives that
evidence. Each principle gives its reason and a question that a reviewer can answer from
evidence: a test result, a mutant result or the text of the code.

Other sources own other facts. This document does not copy them:

- [CONTEXT.md](../CONTEXT.md) defines the project terms, for example Kernel, Source,
  Target, Plan Step, Failure Code and Target Commit.
- [docs/testing.md](testing.md) owns the operational rules: the
  [ownership areas](testing.md#ownership-areas), the
  [shared test modules](testing.md#shared-test-modules), the
  [verification tiers](testing.md#verification-tiers), the
  [CI gates](testing.md#ci-gates), and the steps of the
  [test quality checks](testing.md#test-quality-checks).
- The docstring of each shared module and helper states its contract.
- `RULES.md`, when your checkout has one, gives the general test rules, for example that
  a fake is not the only evidence of real integration behavior. It is a local file that
  Git ignores, so this document does not link it.
- The
  [case study](https://github.com/aigengame/aseprite-automation/wiki/Case-Study-Tests-That-Could-Not-Fail-or-Added-Nothing-(SPA-Test-Architecture-Refactor))
  records the cases behind each principle: the tests, the mutants and the results.

## 1. The test can disprove its claim

A test gives evidence only when it fails when its claim is false. The input must reach
the rule that the test names. Argument parsing, the request schema or another limit can
refuse the input first, and then the rule does not run. The assertion must accept the
results that the claim allows, and no other result. Any nonzero exit, or a Failure Code
without its reason, also accepts an unrelated failure, for example an Aseprite launch
failure. An assertion that no result can break holds nothing. When a correct value can
change from run to run, assert a pattern that accepts each correct value. A limit needs
the accepted case at the limit and the refused case one step after it. With only one of
them, a wrong limit or a check that refuses every input passes. An injected fault must
be the cause of the failure that the test asserts, and it must not change data that
another case uses.

**Question:** Which wrong implementation makes this test fail, and does the failure come
from the rule that the test names?

## 2. The evidence is independent and sufficient

An expected value that the test builds from the code under test changes when the code
changes, so the test passes by construction. A round trip through a writer and a reader
that change together cannot fail either. An observer that records only some facts passes
a defect in a fact that it does not record. An observer that shares code with the
subject cannot find a defect in that code. The assertions must depend on the behavior
under test. In an e2e test, they must depend on what the Kernel or Aseprite did. If they
do not, the test passes when its subject did not run.

**Question:** Where does the expected value come from, and which fact that the subject
can change does the test not observe?

## 3. The test runs in the appropriate tier

Each tier has a cost and a scope. Use the least costly tier that can establish the
claim. An e2e test whose subject does not need the Kernel uses Aseprite time, and the
pull request job does not run it, so it gives no evidence there. The file name must name
the tier in which the test runs. A test gives evidence only where it runs and passes. A
test that skips in each job, or that runs on one platform only, gives no evidence in
the other jobs or platforms.

**Question:** What is the least costly tier that can establish the claim, and in which
jobs and on which platforms does the test run and pass?

## 4. Each claim has a clear owner

A test that repeats a claim that another test at the same tier holds cannot fail unless
the other test fails too. It adds run time and one more place to change. An assertion
that a helper or the subject already makes is also a repeat. A test at a different tier
is not a repeat. A rule that the members of a closed set share, for example the
commands, the Failure Codes or the Plan-eligible Operations, belongs in one table. The
table has one row for each member and a guard that keeps the rows equal to the set.
With a test for each member, a member that has no test can break the rule. A guard that
reads the same predicate as the table, accepts a false exemption, or misses a source of
members cannot fail. A row covers only the code path that its request takes, so a
different path needs its own test.

**Question:** Which test owns this claim, and which test fails when a new member of the
set has no row?

## 5. The test reuses the existing helpers by their contracts

A private copy of the invocation steps can differ from the shared test module. It can
hide an assertion, use a different time limit, or keep a defect that the shared module
does not have. Start SPA, Aseprite and Lua fixtures through the shared test modules, and
use the helpers of the ownership area and the tables of principle 4. Use each helper
only in the cases that its contract covers. For example, a helper that requires a Target
does not fit a request that has no Target. When a helper does not accept the input that
a test needs, extend the helper. Do not write a private copy.

**Question:** Does the test start SPA, Aseprite and Lua fixtures through the shared test
modules, and does each helper that it uses agree with the contract of that helper?

## 6. A refactor keeps the verification

When a test moves, or another test replaces it, an assertion or an exercised code path
can be lost. The claim then has no test, and no test fails. A name, docstring or comment
that claims more than the test checks makes a reader believe that the coverage exists.
When you change a test, change the text that describes it in the same change.

**Question:** For each assertion and code path of the old test, which test holds it now?
Does each sentence that describes the test agree with its code?

## How to get the evidence

The [mutant check](testing.md#mutant-check) runs a test against code that is wrong on
purpose. It answers the questions of principles 1, 2, 4 and 6. The
[stand-in Aseprite run](testing.md#stand-in-aseprite-run) finds e2e tests that do not
need the Kernel, or that do not check what the Kernel did. It answers the questions of
principles 2 and 3.
