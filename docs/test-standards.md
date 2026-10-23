# Test standards

Read this document before you write or change a test.

A test is useful when three things are true: it fails when its claim is false, no
other test at the same tier holds the same claim, and it runs in the fastest tier that
can hold the claim. Each section below names a defect that breaks one of these, or that
hides such a defect from a reader. It tells why a test with the defect cannot fail or
adds nothing, and it gives a check that finds the defect.

Other sources own other facts. This document does not copy them:

- [CONTEXT.md](../CONTEXT.md) defines the project terms, for example Kernel, Source,
  Target, Cel, Plan Step, Failure Code and Target Commit.
- [docs/testing.md](testing.md) owns the operational rules: the
  [verification tiers](testing.md#verification-tiers), the
  [routine commands](testing.md#routine-verification-commands), the
  [shared test modules](testing.md#shared-test-modules) and the rules for their use,
  [shared native parallel execution](testing.md#shared-native-parallel-execution), the
  [CI gates](testing.md#ci-gates), and the
  [platform and display requirements](testing.md#platform-and-display-requirements).
- The shared test modules own the invocation steps. The rule tables own the rules that
  a set of commands shares. "Where a test goes" names the tables.
- `RULES.md`, when your checkout has one, gives the general test rules, for example that
  a fake is not the only evidence of real integration behavior. It is a local file that
  Git ignores, so this document does not link it.

## Where a test goes

**The tier.** The file name gives the tier: `test_unit_*`, `test_integration_*` or
`test_e2e_*` ([verification tiers](testing.md#verification-tiers)). The `e2e` marker
means that the test needs a real Aseprite ([`pyproject.toml`](../pyproject.toml)). The
pull request job runs only the tests without the `e2e` marker, and only on Linux
([CI gates](testing.md#ci-gates)).

**The invocation module.** Start SPA, Aseprite and Lua fixtures through the shared test
modules. [Shared test modules](testing.md#shared-test-modules) lists them and gives the
rules for their use. A Plan e2e test builds its request with `plan_request` and reads
its result with `observe_plan`, in [`tests/plan/support.py`](../tests/plan/support.py).

**A rule that a set of commands or Operations shares.** One table holds the rule for
the whole set, with one row for each member and a guard that keeps the rows equal to
the set. For a new member, add a row or let the predicate of the table add it. Do not
write a test of the rule for one member. The guard fails until the new member has a row
or an exemption with a true reason. The tables:

- Request, runtime, Edit-file and export destination rules for each command: the tables
  in [`tests/contracts/`](../tests/contracts/) that use
  [`tests/contracts/command_rules.py`](../tests/contracts/command_rules.py). Its module
  docstring tells how the rows and the exemptions work.
- Plan rules for each Plan-eligible Operation:
  [`tests/plan/test_e2e_plan_rules.py`](../tests/plan/test_e2e_plan_rules.py), and the
  Cel rejection rule in
  [`tests/cel/test_unit_rejection_consumers.py`](../tests/cel/test_unit_rejection_consumers.py).
- Filter rules for each Operation Filter: the tables that
  [`tests/filter/test_integration_filter_correspondence.py`](../tests/filter/test_integration_filter_correspondence.py)
  keeps equal to the Operations.
- Failure Codes and runtime issue kinds:
  [`tests/contracts/test_unit_failures.py`](../tests/contracts/test_unit_failures.py).

A row covers only the code path that its request takes. Keep a separate test for a path
that no row takes.

## A test must be able to fail

### The expected value comes from the code under test

The test builds its expected value from the constant or the function that it tests. A
change to the code changes the expected value too, so the test passes by construction.
A round trip through an SPA writer and an SPA reader that change together cannot fail
either.

**Check:** Write the expected value as a literal. Or take it from a source that does not
share code with the subject: a third-party decoder, or a Lua fixture that loads no
Kernel module. A mutant of the constant or the function must fail the test.

### The assertion is weaker than the claim

The assertion accepts a result that the claim excludes. Examples: any nonzero exit, a
Failure Code without the reason, a subset where the claim is an equal set, and
`pytest.raises` without `match`. Another check that fails with the same code then
passes the test. An assertion that no result can break, for example a file pattern that
never matches the real name, also holds nothing.

**Check:** Assert the exact exit status, the Failure Code, and the reason or the
details. Assert the whole set. Use a mutant that keeps the failure path and changes
only the fact that the test claims, for example a different reason with the same code.
The test must fail.

Assert only what the subject fixes. When a value can change from run to run, for
example an order that comes from a Lua table, assert a pattern that accepts each correct
value. Run such an e2e test more than once before you merge it.

### The input does not reach the rule

An earlier check refuses the input before the rule that the test names: argument
parsing, the request schema, another validation, or another limit. The rule never runs,
so a defect in it passes the test.

**Check:** Read the reason in the result. It must come from the rule that the test
names. Start from an accepted input and change one property. A mutant that removes the
rule must fail the test.

### The test has no case at each side of the limit

The test gives only an input that the rule refuses, or only an input far from the
limit. A wrong limit, or a check that refuses every input, then passes the test.

**Check:** Add the accepted case at the limit and the refused case one step after it.
A mutant that moves the limit by one in each direction must fail one of the two cases.
A mutant that refuses every input must fail the accepted case.

### The test passes when its subject did not run

The assertions do not depend on what the Kernel or Aseprite did. An expected failure
can come from an unrelated failure, for example an Aseprite launch that failed. A test
can also run a tool and no SPA code, or skip in every job that runs it.

**Check:** Do the stand-in Aseprite run below. Assert a fact that only a real run gives.
In a refusal test, assert the reason, so that a launch failure fails the test. Read the
passed and skipped counts of each job that must run the test. A test that skips there gives no
evidence there. A test that runs only on macOS or Windows gives local evidence only.

### A fault injection cannot trip

The test injects a fault, but the fault does not cause the failure that the test
asserts. The code does not read the place of the fault. An earlier check stops the
action first. A fake does not make the whole condition, so the step fails for another
reason. Or the fault changes data that a later case also uses.

**Check:** Remove the fault, and run the test. It must fail. Then read the failure with
the fault: it must come from the fault. Inject the fault through the seam that the code
reads. For an SPA adapter of the CLI process, use a seam of
[`tests/fixtures/observe_cli.py`](../tests/fixtures/observe_cli.py). Give each case its
own copy of the data that a fault changes.

### The observer does not record a fact that the subject can change

The test reads the result through an observer that records only some facts. A defect
that changes a fact that the observer does not record passes the test. Examples: the Cel
position, the RGB values under alpha 0, and an envelope that the observer does not
validate.

**Check:** List the facts that the subject can change, in the terms of CONTEXT.md. For
each fact, a mutant that changes only that fact must fail the test. An observer that
compares the Kernel with itself cannot find a Kernel defect. Use an observer that loads
no Kernel module. Validate each envelope against the schema of its command, with
`validate_envelope` in [`tests/native_invocation.py`](../tests/native_invocation.py).

### A coverage guard cannot fail

A table, a hand-written list or a set of cases must cover a closed set: the commands,
the Failure Codes, the resources or the issue kinds. With no guard, a new member gets no
row, and no test fails. A guard can also fail to fail: it reads the same predicate as
the table, it accepts a false exemption, or it does not read every place that makes a
member.

**Check:** Compare the table with a set that the product code gives, and with a literal
expected set or count. Run three mutants against the guard: remove one row, add one
member to the set, and add a false exemption. Each must fail the guard.

## Each claim has one test, in the fastest tier that can hold it

### A test repeats a claim that another test at the same tier holds

The second test cannot fail unless the first one fails too. It adds run time and one
more place to change. An assertion that a helper or the subject already makes is also a
repeat: the earlier check fails first, and the assertion never decides.

**Check:** Before you add a test, search for a test that asserts the same claim at the
same tier. A mutant that the new test finds must not be found by the old test as well.
A test at a different tier is not a repeat, for example a fast refusal row and an e2e
test of the native result.

### The tests repeat a shared rule for each command

Each command of a set has its own test of a rule that the whole set obeys. A command
with no such test can break the rule, and no test fails.

**Check:** When the expected answer does not depend on the command, hold the rule in one
table with a guard (see "Where a test goes").

### A test copies the invocation steps

The test resolves the CLI, starts the process, sets a time limit or checks the exit
status in a private helper. Each copy is one more place that can differ from the shared
module. A copy can hide an assertion, use a different time limit, or keep a defect that
the shared module does not have.

**Check:** Search the test module for `subprocess`, `shutil.which` and `--script`.
Replace each copy with the shared module, by the rules in
[shared test modules](testing.md#shared-test-modules). When a shared builder does not
take the input that your test needs, extend the builder. Do not write a private copy.

### The test runs in a slower tier than its subject needs

An e2e test whose subject does not need the Kernel takes Aseprite time, and it runs
only where Aseprite is available. The pull request job does not run it, so it gives no
evidence there. A refusal that SPA makes before the Kernel call is
not an e2e case. A file name that names a faster tier than the test runs is also wrong.

**Check:** Do the stand-in Aseprite run below. Move each test whose subject does not
need the Kernel to the fast tier, with a controlled Aseprite executable. Delete it when
a fast test holds its claim. A test that starts a process is not a `unit` test.

## When you move, replace or delete a test

### A replacement or a deletion loses an assertion

The new test, or the test that "holds" the claim of a deleted test, does not assert
everything that the old test asserted. Examples: the diagnostics, the files after the
CLI call, and the schema of the failure envelope. The lost assertion then has no test.

**Check:** List each assertion of the old test. For each one, name the test that asserts
it now, with an input that takes the same code path. When no test asserts it, keep the
old test or add the assertion. A mutant that only the old test finds shows a loss.

### A name, docstring or comment claims more than the test checks

A test name, a module docstring or a comment names a check, an input, a count or an
independent oracle that the test does not have. A reader trusts the text to find
coverage, and does not add the missing test.

**Check:** Read each sentence against the code. When you move, delete or change a test,
change the text that describes it in the same change. Do not write a count of tests or
cases in a docstring.

## Checks

The commands are for a POSIX shell on macOS or Linux. Run them in the project
environment ([routine commands](testing.md#routine-verification-commands)).

### Mutant check

A mutant is the code under test, made wrong on purpose. A test that passes against it
cannot find that defect.

1. Run `git status --short -- src`. If it shows a change, save a copy of the file first.
2. Find the line in `src/` that the claim of the test depends on. For a Kernel rule, the
   line can be in a Lua file under `src/spa/kernel/`.
3. Change only that line to the wrong behavior that the test must find. Keep the path of
   the result, and change only the fact that the test claims.
4. Remove the bytecode cache:

   ```sh
   find src tests -name __pycache__ -prune -exec rm -rf {} +
   ```

   CPython uses a cached `.pyc` file when the source has the same size and the same
   modification time in whole seconds. A mutant of the same length that you make in the
   same second then does not run.
5. Make sure that `SPA_TEST_INSTALLED_CLI` is not set. A wheel-installed CLI does not
   run the code of your checkout.
6. Run the test. It must fail. When the test replaces an old test, run the old test
   against the same mutant too.
7. Read the `E` line of the failure. It must be the assertion of the claim. These do not
   show that the test finds the defect:
   - an import error or a crash;
   - a `runtime_incompatible` failure from the runtime probe. A mutant in a Lua module
     that the probe loads stops the probe. Change the handler entry file instead;
   - a failure that the old test and the new test both have. Such a mutant does not
     show a difference between them. Choose a mutant that keeps the failure path.
8. When the mutant does not change the result for the input of the test, it is an
   equivalent mutant. Choose another mutant.
9. Restore the file from Git or from your copy, and remove the cache again. Make sure
   that `git status --short -- src` shows what it showed in step 1.
10. Record each mutant, the result of the old test and the result of the new test in the
    pull request description. When no mutant can isolate a check, write that under "Not
    verified".

### Stand-in Aseprite run

The stand-in is an executable that forwards the runtime probe to the real Aseprite. It
records the test that makes a Kernel call, and it fails that call with exit status 1. It
runs every other call, for example a Lua fixture, with the real Aseprite. An e2e test
that passes on the stand-in with no Kernel call did not need the Kernel.

The stand-in tells the calls apart by their arguments. The probe runs the packaged
`runtime/probe.lua`. The probe and each Kernel call pass a script parameter `request=`,
so the stand-in checks for the probe first. A Lua fixture can pass `response=`, so that
argument does not identify a Kernel call.

1. Set `SPA_TEST_ASEPRITE` to your real Aseprite executable. Make the stand-in:

   ```sh
   D=$(mktemp -d)
   A=$(realpath "$SPA_TEST_ASEPRITE")
   for d in "${A%/*}/../Resources/data" "${A%/*}/../data" "${A%/*}/data"; do
     if [ -f "$d/gui.xml" ]; then
       ln -s "$(realpath "$d")" "$D/data"
       break
     fi
   done
   cat > "$D/aseprite" <<EOS
   #!/bin/sh
   case " \$* " in
     */runtime/probe.lua*) exec "$A" "\$@" ;;
     *" request="*) printf '%s\n' "\$PYTEST_CURRENT_TEST" >> "$D/calls.log"; exit 1 ;;
     *) exec "$A" "\$@" ;;
   esac
   EOS
   chmod +x "$D/aseprite"
   ```

   The stand-in must be a regular file. Runtime discovery looks for `data/gui.xml`
   next to it, so the loop links the `data` directory of the real Aseprite there.
2. Run the e2e tier against the stand-in, with a summary line for each passed case:

   ```sh
   SPA_TEST_ASEPRITE="$D/aseprite" uv run --frozen --group test \
     pytest -m "e2e and not slow" -n 0 -rp > "$D/run.txt"
   ```

   On macOS, an Aseprite launch can stop before its script runs. When a case stops,
   run it again alone.
3. Compare the passed cases with the cases that made a Kernel call:

   ```sh
   sed -n 's/^PASSED //p' "$D/run.txt" | LC_ALL=C sort -u > "$D/passed.txt"
   sed 's/ ([a-z]*)$//' "$D/calls.log" | LC_ALL=C sort -u > "$D/called.txt"
   LC_ALL=C comm -23 "$D/passed.txt" "$D/called.txt"  # passed, no Kernel call
   LC_ALL=C comm -12 "$D/passed.txt" "$D/called.txt"  # passed, Kernel called
   ```

4. Examine each listed case:
   - Passed with no Kernel call: the test did not need the Kernel. When its claim is
     the runtime probe, a caller-owned Lua script or a behavior of Aseprite itself, it
     stays in the e2e tier.
     Otherwise delete it when a fast test holds its claim, or move it to the fast tier.
     Read its Lua fixture first: a fixture that runs a Kernel handler with `dofile`
     passes no `request=` argument, so the stand-in does not see that Kernel call.
   - Passed with a Kernel call: the test does not check what the Kernel did. Assert a
     fact that only a real run gives. A test that asserts that the Kernel call fails
     passes here correctly.

The run has limits:

- A process that does not get `PYTEST_CURRENT_TEST` from pytest, for example an MCP
  server process, writes an empty line to the log. The log does not name the case of
  that Kernel call.
- The run lists only cases that pass. A test that fails on the stand-in for an unrelated
  reason, for example an error in a test helper, is not in the lists. Read why such a
  case fails.

## Cases

The wiki page
[Case Study: Tests That Could Not Fail or Added Nothing](https://github.com/aigengame/aseprite-automation/wiki/Case-Study-Tests-That-Could-Not-Fail-or-Added-Nothing-(SPA-Test-Architecture-Refactor))
shows each defect as it was found in this repository, with the mutants and the results.
