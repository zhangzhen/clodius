import argparse
import os
import sys


from cooler.contrib import recursive_agg_onefile
import tileBedFileByImportance, tile_bigWig

def main():

    parser = argparse.ArgumentParser(
        description="Wrapper around conversion tools available for higlass")
    parser.add_argument(
        '-i', '--input_file', help="Path to input file", required=True)
    parser.add_argument(
        '-o', '--output_file', help="Path of output file", required=False)
    parser.add_argument(
        '-d', '--data_type', choices=[
            "bigwig", "cooler", "gene_annotation", "hitile"],
        help='Data Type of input file.', required=True)
    parser.add_argument(
        '-n', '--n_cpus',
        help='Number of cpus to use for converting cooler files',
        required=False, default=1)

    args = vars(parser.parse_args())

    data_type = args["data_type"]
    input_file = args["input_file"]
    output_file = args["output_file"]
    n_cpus = args["n_cpus"]


    if output_file is None:
        output_file = format_output_filename(input_file, data_type)

    if output_file == "-":
        sys.stdout.write("Output to stdout")

    if data_type in ["bigwig", "hitile"]:
        sys.argv = ["fake.py", input_file, "-o", output_file]
        tile_bigWig.main()

    if data_type == "cooler":
        recursive_agg_onefile.main(
            input_file, output_file, int(10e6), n_cpus=n_cpus)

    if data_type == "gene_annotation":
        sys.argv = ["fake.py", input_file, output_file]
        tileBedFileByImportance.main()


def format_output_filename(input_file, data_type):
    """
    Takes an input_file and data_type and returns the properly
    formatted output filename
    :param input_file: String
    :param data_type: String
    """

    input_file_basename = os.path.basename(input_file)

    file_extentions = {
        "gene_annotation" : "bed",
        "hitile" : "hitile",
        "cooler" : "cool",
        "bigwig": "bw"
    }

    return "{}.multires.{}".format(
        input_file_basename.rpartition(".")[0], file_extentions[data_type])


if __name__ == '__main__':
    main()
