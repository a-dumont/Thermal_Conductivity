"""
This code is both a module and a python executable script meant to
analyse data from thermal conductivity experiment. This code should
support both the VTI and Tallahassee probes with and without magnetic
field. To use interactively import as module in Ipython or jupyter and
see docstrings provided within the code using function? in Ipython/juyter.
To use as a script simply run:
                python this_script.py /data/my_data.dat w t L
Where w, t and L are the dimensions of the sample. Using the script all
Figures will be saved as one pdf in /figures/my_data.pdf using the same
directory structure as the data folder.
"""
import sys
import os
import datetime

import numpy as np
import numpy.polynomial.polynomial as npp

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import ThermalConductivity.Analysis.Functions.__functions as F
import ThermalConductivity.Utilities.__utilities as U
import ThermalConductivity.Utilities.Database.__database as D
import ThermalConductivity.Visualization.__plots as V
import ThermalConductivity.Comparison.__Comparison as Comp
from ThermalConductivity.Analysis.__base_class import Measurement
from ThermalConductivity.Thermometry.__Thermometry import seebeck_thermometry

################################################################################
#                          ____ _        _    ____ ____                        #
#                         / ___| |      / \  / ___/ ___|                       #
#                        | |   | |     / _ \ \___ \___ \                       #
#                        | |___| |___ / ___ \ ___) |__) |                      #
#                         \____|_____/_/   \_\____/____/                       #
################################################################################


class Conductivity(Measurement):
    """
    This is the main class of the program. It contains all the
    data and other information about the sample. Also contains
    all the analysis functions for both probes.
    """

    def __init__(self, filename=None, w=1e-6, t=1e-6, L=1e-6, sign=1, **kwargs):
        # Initialize the Measurement class
        super().__init__()

        # Add dictionnaries
        self["dict_measures"] = D.measurements_dict
        self["dict_raw"] = D.raw_data_dict
        self["dict_parameters"] = D.parameters_dict

        # Check for some specific kwargs and update kwargs
        self["force_kxy"], kwargs = self.__check_force_kxy(**kwargs)
        self["symmetrize"], kwargs = self.__check_symmetrize(**kwargs)
        self["sign"] = self.__check_sign(sign)
        self["gain"], kwargs = self.__check_gain(**kwargs)

        if filename is not None:
            filename = os.path.abspath(filename)
            self["filename"] = filename
            self["filetype"] = self.__check_filetype(filename)

            # Find info
            self.__add_parameters(w, t, L)

            # If the file contains raw data
            if self["filetype"] == "raw":

                # If symmetrize is True
                if self["H"] != "0.0" and self["symmetrize"] is True:
                    filename2 = U.get_symetric_file(filename)
                    if filename2 is None:
                        self["symmetrize"] = False
                        if filename.find("--") != -1:
                            self["H"] = "-"+self["H"]
                            raw_data = U.read_file_raw(filename)
                        else:
                            raw_data = U.read_file_raw(filename)
                    else:
                        raw_data = self.__Symmetrize(filename, filename2)
                elif self["H"] != "0.0" and self["symmetrize"] is False:
                    if filename.find("--") != -1:
                        self["H"] = "-"+self["H"]
                        raw_data = U.read_file_raw(filename)
                    else:
                        raw_data = U.read_file_raw(filename)

                else:
                    raw_data = U.read_file_raw(filename)

                for key, values in raw_data.items():
                    self.Store_as_raw_data(values,key)

                self.__Analyze(self["gain"])
                self.__add_measure()

            # If the file contains treated data
            elif self["filetype"] == "treated":
                data = U.read_file_treated(filename)

                for key, values in data.items():
                    self.Store_as_measure(values,key)
                    self.__add_measure()

        # Remaining kwargs are set as parameters
        for key, value in kwargs.items():
            self.Store_as_parameter(value,key)
        return

    def __check_force_kxy(self, **kwargs):
        try:
            answer = kwargs["force_kxy"]
            kwargs.pop("force_kxy")
            if type(answer) is bool:
                pass
            else:
                raise TypeError("force_kxy must be True or False")
        except KeyError:
            answer = False
        return answer, kwargs

    def __check_symmetrize(self, **kwargs):
        try:
            answer = kwargs["symmetrize"]
            kwargs.pop("symmetrize")
            if type(answer) is bool:
                pass
            else:
                raise TypeError("symmetrize must be True or False")
        except KeyError:
            answer = True

        return answer, kwargs

    def __check_sign(self, sign):
        if sign in [1, -1]:
            answer = sign
        else:
            raise ValueError("Sign must be 1 or -1")
        return sign

    def __check_gain(self, **kwargs):
        if "gain" in kwargs:
            answer = kwargs["gain"]
            kwargs.pop("gain")
        else:
            answer = 1000

        return answer, kwargs

    def __check_filetype(self, filename):
        filename = os.path.abspath(filename)
        columns = U.read_header(filename)[-1].split("\t")

        raw_data = 0
        measures = 0
        for key, values in self["dict_raw"].items():
            for v in values:
                if v in columns:
                    raw_data += 1
                else:
                    measures += 1

        if raw_data > measures:
            filetype = "raw"
        else:
            filetype = "treated"

        return filetype

    def __Symmetrize(self, filename, filename2):
        anti_sym = ["dTy_0", "dTy_Q"]

        if filename.find("--") != -1:
            filename, filename2 = filename2, filename
        else:
            pass

        data = U.read_file_raw(filename)
        data2 = U.read_file_raw(filename2)

        n = len(data["T0"])
        n2 = len(data2["T0"])

        if n != n2:
            if abs(data["T0"][0]-data2["T0"][0]) <= 0.1:
                if n > n2:
                    for key in data:
                        data[key] = data[key][0:n2]
                else:
                    for key in data2:
                        data2[key] = data2[key][0:n]
            elif abs(data["T0"][-1]-data2["T0"][-1]) <= 0.1:
                if n > n2:
                    for key in data:
                        data[key] = data[key][abs(n-n2):]
                else:
                    for key in data2:
                        data2[key] = data2[key][abs(n-n2):]
            else:
                if n > n2:
                    for key in data:
                        data[key] = data[key][0:n2]
                else:
                    for key in data2:
                        data2[key] = data2[key][0:n]

        sym_data = dict()

        for key, values in data.items():
            if key in data2:
                if key in anti_sym:
                    sym_data[key] = 0.5*(data[key]-data2[key])
                else:
                    sym_data[key] = 0.5*(data[key]+data2[key])
            else:
                pass

        return sym_data

    def __Analyze(self, gain):
        if self["probe"] == "Tallahassee":
            self.__tlh_analysis(gain)
        elif self["probe"] == "VTI":
            self.__vti_analysis(gain)

    def __tlh_analysis(self, gain):
        self.__remove_uncalibrated_points()
        self.__compute_and_store_tlh_physical_properties(gain)
        if self["H"] != "0.0" or self["force_kxy"]:
            self.__compute_and_store_dTy_and_kxy(gain)

    def __remove_uncalibrated_points(self):
        index = np.where(self["R+_Q"] < self["R+_0"][-1])
        for i in self.raw_data:
            self[i] = np.delete(self[i], index)

    def __compute_and_store_tlh_physical_properties(self, gain):
        # Get I and T0
        I = self["I"]
        T0 = self["T0"]

        # Compute T+ and T-
        Tp = F.tallahassee_temp(self["R+_0"], self["R+_Q"], T0)
        Tm = F.tallahassee_temp(self["R-_0"], self["R-_Q"], T0)

        # Compute T_av dTx and kxx
        T_av = 0.5*(Tp+Tm)
        dTx = (Tp-Tm)
        kxx = F.compute_kxx(I, dTx, self["w"], self["t"], self["L"])

        # Store values in self
        self.Store_as_measure(T_av, "T_av")
        self.Store_as_measure(Tp, "Tp")
        self.Store_as_measure(Tm, "Tm")
        self.Store_as_measure(dTx, "dTx")
        self.Store_as_measure(kxx, "kxx")

    def __vti_analysis(self, gain):
        self.__compute_and_store_vti_physical_properties(gain)
        if self["H"] != "0.0" or self["force_kxy"]:
            self.__compute_and_store_dTy_and_kxy(gain)

    def __compute_and_store_vti_physical_properties(self, gain):
        dTabs_0, dTabs_Q = self["dTabs_0"], self["dTabs_Q"]
        dTx_0, dTx_Q = self["dTx_0"], self["dTx_Q"]
        T0 = self["T0"]
        I = self["I"]

        # Compute physical properties
        physicial_properties = F.vti_thermocouple_calibration_loop(
            dTabs_0, dTabs_Q, dTx_0, dTx_Q, T0, gain)
        for key, value in physicial_properties.items():
            self.Store_as_measure(value, key)

        # Compute kxx
        kxx = F.compute_kxx(
            I, physicial_properties["dTx"], self["w"], self["t"], self["L"])
        self.Store_as_measure(kxx, "kxx")

    def __compute_and_store_dTy_and_kxy(self, gain):
        # Compute dty
        reference_temperature = (self["T0"] + self["T_av"]) / 2
        dTy = F.compute_thermocouple(
            self["dTy_0"], self["dTy_Q"], reference_temperature, gain)
        dTy *= self["sign"]
        self.Store_as_measure(dTy, "dTy")

        # Compute kxy
        kxy = F.compute_kxy(
            self["kxx"], self["dTx"], dTy, self["w"], self["L"])
        self.Store_as_measure(kxy, "kxy")

    def __add_parameters(self, width, thickness, length):

        filename = self["filename"]
        header = U.read_header(filename)
        parameters = []

        # Geometric parameters
        self.Store_as_parameter(width, "w")
        self.Store_as_parameter(thickness, "t")
        self.Store_as_parameter(length, "L")

        # Other parameters
        self.Store_as_parameter(U.find_H(filename, header), "H")
        self.Store_as_parameter(U.find_date(filename, header), "date")
        self.Store_as_parameter(U.find_mount(filename, header), "mount")
        self.Store_as_parameter(U.find_sample(filename, header), "sample")
        self.Store_as_parameter(U.find_probe(filename, header), "probe")

        return

    def __add_measure(self):
        if "T_av" and "kxx" in self.measures:
            self.measures.append("kxx/T")
            self["kxx/T"] = self["kxx"]/self["T_av"]
        else:
            pass

        if "T_av" and "dTx" in self.measures:
            self.measures.append("dTx/T")
            self["dTx/T"] = self["dTx"]/self["T_av"]*100
        else:
            pass

        if "T_av" and "T0" and "dTx" in self.measures:
            self.measures.append("Resistance")
            self["Resistance"] = (self["T_av"]-self["T0"])/self["dTx"]
        else:
            pass

        if "dTx" and "dTy" in self.measures:
            self.measures.append("dTy/dTx")
            self["dTy/dTx"] = self["dTy"]/self["dTx"]*100
        else:
            pass

        if "kxx" and "kxy" in self.measures:
            self.measures.append("kxy/kxx")
            self["kxy/kxx"] = self["kxy"]/self["kxx"]*100
        else:
            pass

        if "T_av" and "kxy" in self.measures:
            self.measures.append("kxy/T")
            self["kxy/T"] = self["kxy"]/self["T_av"]
        else:
            pass

        if "T_av" and "kxy" in self.measures:
            if self["H"] != "0.0":
                self.measures.append("kxy/TH")
                try:
                    H = float(self["H"])
                    self["kxy/TH"] = self["kxy"]/self["T_av"]/H
                except ValueError:
                    pass
            else:
                pass
        else:
            pass

        if "Tp" and "Tm" in self.measures:
            self.measures.append("Tp_Tm")
            self["Tp_Tm"] = None

        return

    def Plot(self, key, *args, **kwargs):
        """
        Used as a layer between the object and Visualization.Plot

        Parameters:
        ------------------------------------------------------------------------
        key:        string
                    The measurement to plot

        Kwargs:
        ------------------------------------------------------------------------
        show:       Bool
                    Determines if the figure is shown ore closed defaults to True

        parameters: list
                    list of parameters to be used for legends

        axis_fs:    Int
                    The axis labels fontsize

        fig:        matplotlib.figure
                    Used to draw on an existing figure, requires ax

        ax:         matplotlib.ax
                    Used to draw on an existing figure, requires fig

        x_axis:     string
                    The measurement to use as x-axis defaults to T_av
        """

        # Deal with kwargs
        if "fig" in kwargs:
            return_fig = False
        else:
            return_fig = True

        if "x_axis" in kwargs:
            x_axis = kwargs["x_axis"]
            kwargs.pop("x_axis")
            if x_axis in self.measures or x_axis in self.raw_data:
                pass
            else:
                raise Exception(
                    "x_axis must be in self.measures or self.raw_data")
        else:
            x_axis = "T_av"

        if "figtext" not in kwargs:
            kwargs["figtext"] = self["sample"]
        else:
            pass

        if "parameters" in kwargs:
            parameters = dict()
            parameters_list = kwargs["parameters"]
            kwargs.pop("parameters")
            for p in parameters_list:
                if p in self.parameters:
                    parameters[p] = self[p]
                else:
                    raise Exception("parameters must be in self.parameters")
        else:
            parameters = dict()

        kwargs["parameters"] = parameters

        if key != "Tp_Tm":

            xdata, xkey = self[x_axis], x_axis
            ydata, ykey = self[key], key

            fig, ax = V.Plot(xdata, ydata, xkey, ykey, *args, **kwargs)

        else:

            xdata, xkey = self[x_axis], x_axis
            ydata1, ykey1 = self["Tp"], "Tp"
            ydata2, ykey2 = self["Tm"], "Tm"

            if "show" in kwargs:
                show = kwargs["show"]
                kwargs["show"] = None
            else:
                kwargs["show"] = None
                show = True
            kwargs["parameters"]["which"] = r"T$^{+}$"
            fig, ax = V.Plot(xdata, ydata1, xkey, ykey1, *args, **kwargs)

            kwargs["show"] = show
            kwargs["parameters"]["which"] = r"T$^{-}$"
            kwargs["fig"], kwargs["ax"] = fig, ax
            fig, ax = V.Plot(xdata, ydata2, xkey, ykey2, *args, **kwargs)

        if return_fig is False:
            return

        else:
            return fig, ax

    def Plot_all(self, *args, **kwargs):
        """
        Plots all non trivial measures, all the same kwargs as Conductivity.Plot
        with the addition of filename to save the file.
        """

        remove = ["T_av", "T0", "Tp", "Tm", "T0_fit", "I_fit"]
        measures = [i for i in self.measures if i not in remove]
        figures = []

        try:
            filename = kwargs["filename"]
            kwargs.pop("filename")
        except KeyError:
            filename = None

        try:
            overwrite = kwargs["overwrite"]
            kwargs.pop("overwrite")
        except KeyError:
            overwrite = "ask"

        for key in measures:
            figures.append(self.Plot(key, *args, **kwargs)[0])

        if filename is not None:
            filename = os.path.abspath(filename)
            U.save_to_pdf(filename, figures, overwrite=overwrite)
        else:
            pass

        return

    def Plot_fancy(self, *args, **kwargs):
        """
        Just like Plot_all but with a fancy layout that is more suited to
        ipython notebooks
        """

        remove = ["T_av", "T0", "Tp", "Tm", "I_fit", "T0_fit"]

        measures = [i for i in self.measures if i not in remove]
        ref_meas = ["kxx", "kxx/T", "kxy", "kxy/kxx", "dTx",
                    "dTx/T", "dTy", "dTy/dTx", "Resistance", "Tp_Tm"]
        measures = [i for i in ref_meas if i in measures]

        n = len(measures)

        fig, ax = V.create_grid(n)

        try:
            show = kwargs["show"]
            kwargs.pop("show")
        except KeyError:
            show = None

        try:
            filename = kwargs["filename"]
            kwargs.pop("filename")
        except KeyError:
            filename = None

        try:
            overwrite = kwargs["overwrite"]
            kwargs.pop("overwrite")
        except KeyError:
            overwrite = "ask"

        for i in range(n):
            self.Plot(measures[i], *args, show=None,
                      fig=fig, ax=ax[i], **kwargs)

        if hasattr(self, "__sample") is True:
            plt.suptitle(self["sample"], y=0.95, fontsize=22)
        else:
            pass

        fig.tight_layout(rect=[0.01, 0.01, 1, 0.96])

        if filename is not None:
            filename = os.path.abspath(filename)
            U.save_to_pdf(filename, fig, overwrite=overwrite)
        else:
            pass

        if show is True:
            plt.show()
        elif show is False:
            plt.close()
        else:
            pass

        return fig, ax

    def Convert_to_Measurement(self):
        """
        Returns a Comparison.Measurement object
        """

        measurement = Comp.Conductivity()
        for m in self.measures:
            measurement[m] = self[m]
        for p in self.parameters:
            measurement[p] = self[p]

        measurement.measures = self.measures
        measurement.parameters = self.parameters

        return measurement

    def Write_out(self, filename=None, overwrite="ask"):
        """
        Writes the treated data to a file
        """
        if filename is None:
            if self["H"] == "0.0" or self["symmetrize"] is False:
                filename = self["filename"].replace(".dat", "-treated.dat")
            else:
                filename = self["filename"].replace(".dat", "-sym-treated.dat")
        else:
            filename = os.path.abspath(filename)

        parameters1 = ["sample", "date", "mount", "probe", "H"]
        parameters2 = ["w", "t", "L"]
        measures = ["T_av", "T0", "Tp", "Tm", "dTx", "kxx", "dTy", "kxy"]
        columns = ["T_av(K)", "T0(K)", "T+(K)", "T-(K)",
                   "dTx(K)", "kxx(W/Km)", "dTy(K)", "kxy(W/Km)"]
        if self["H"] == "0.0":
            measures = measures[0:6]
            columns = columns[0:6]
        else:
            pass

        columns = "\t".join(columns)

        comments1 = "\n".join(["%s\t=\t%s" % (i, self[i])
                               for i in parameters1])
        comments2 = "\n".join(["%s\t=\t%1.3e" % (i, self[i])
                               for i in parameters2])
        header = comments1+"\n"+comments2+"\n"+columns
        data = np.array([self[i] for i in measures]).T

        U.write_to_file(filename, data, header, overwrite=overwrite)
        return

    def Current(self, _min, _max, deg=5, T_max=100, N=100, *args, **kwargs):
        """
        Used to compute the optimal current function for the sample.

        Parameters:
        ------------------------------------------------------------------------
        _min, _max: int or float
                The min/max of dT/T in percentages

        deg:        int
                The degree of the polynomial fit

        T_max:      int or float
                T0 max for the plot

        N:          int
                Number of points in the plot
        """

        directory = os.path.split(self["filename"])[0]
        rnge = "%1.0f%s_to_%1.0f%s.dat" % (_min, "%", _max, "%")
        name = "_".join([self["sample"].replace(" ", "_"), "dTovT", rnge])
        datafile = os.path.join(directory, name)
        n = self["T_av"].shape[0]
        dT_T = np.linspace(_min/100, _max/100, n)
        alpha = self["w"]*self["t"]/self["L"]
        I = np.sqrt(self["kxx"]*alpha*self["T_av"]*dT_T/5000)
        coeff_I = np.polyfit(self["T0"], I, deg)
        poly_func = np.poly1d(coeff_I)
        T0 = np.linspace(0, T_max, N)
        I_fit = poly_func(T0)

        self["T0_fit"] = T0
        self["I_fit"] = I_fit*1000
        self["coeff_I"] = coeff_I
        self.measures += ["T0_fit", "I_fit"]

        # Looks for show as kwarg
        try:
            show = kwargs["show"]
            if type(show) is not bool:
                if show is not None:
                    raise TypeError("show must be of type bool or None")
                else:
                    kwargs.pop("show")
            else:
                kwargs.pop("show")
        except KeyError:
            show = True

        try:
            filename = kwargs["filename"]
            kwargs.pop("filename")
        except KeyError:
            filename = None

        label = r"$\Delta$ T / T from %1.2f%s to %1.2f%s" % (
            _min, "%", _max, "%")

        fig, ax = self.Plot("I_fit", x_axis="T0_fit", show=None, parameters=[])
        plt.figtext(1-0.005, 0.005, label, fontsize=14,
                    va="baseline", ha="right")

        if show is True:
            plt.show()
        elif show is False:
            plt.close()
        else:
            pass

        if filename is not None:
            filename = os.path.abspath(filename)
            U.save_to_pdf(filename, fig)
        else:
            pass

        try:
            write = kwargs["write"]
            kwargs.pop("write")
        except KeyError:
            write = True

        if write is True:
            degrees = np.array([i for i in range(coeff_I.shape[0])])
            data = np.array([degrees, coeff_I[::-1]]).T
            header = "Current function coefficients\norder\tcoeff"
            U.write_to_file(datafile, data, header, fmt=["%i", "%,18e"])
        else:
            pass

        return

    def Get_known_measures(self):
        return list(self["dict_measures"].keys())

################################################################################
#                       ____   ____ ____  ___ ____ _____                       #
#                      / ___| / ___|  _ \|_ _|  _ \_   _|                      #
#                      \___ \| |   | |_) || || |_) || |                        #
#                       ___) | |___|  _ < | ||  __/ | |                        #
#                      |____/ \____|_| \_\___|_|    |_|                        #
################################################################################


if __name__ == "__main__":

    try:
        filename = sys.argv[1]
    except IndexError:
        raise Exception("First argument must be a filename")
    try:
        w = float(sys.argv[2])
        t = float(sys.argv[3])
        L = float(sys.argv[4])
        sign = int(sys.argv[5])
        sample = Conductivity(filename, w, t, L, sign)
    except IndexError:
        try:
            w = float(sys.argv[2])
            t = float(sys.argv[3])
            L = float(sys.argv[4])
            sample = Conductivity(filename, w, t, L, sign)
        except IndexError:
            sample = Conductivity(filename)
    sample.Plot_all(save=True)
    sample.Write_out()
