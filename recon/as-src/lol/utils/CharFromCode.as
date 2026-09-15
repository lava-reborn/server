class lol.utils.CharFromCode
{
   static var char_list_;
   function CharFromCode(code)
   {
   }
   static function create()
   {
      lol.utils.CharFromCode.char_list_ = new Array();
      lol.utils.CharFromCode.char_list_[27] = "Esc";
      lol.utils.CharFromCode.char_list_[112] = "F1";
      lol.utils.CharFromCode.char_list_[113] = "F2";
      lol.utils.CharFromCode.char_list_[114] = "F3";
      lol.utils.CharFromCode.char_list_[115] = "F4";
      lol.utils.CharFromCode.char_list_[116] = "F5";
      lol.utils.CharFromCode.char_list_[117] = "F6";
      lol.utils.CharFromCode.char_list_[118] = "F7";
      lol.utils.CharFromCode.char_list_[119] = "F8";
      lol.utils.CharFromCode.char_list_[120] = "F9";
      lol.utils.CharFromCode.char_list_[121] = "F10";
      lol.utils.CharFromCode.char_list_[122] = "F11";
      lol.utils.CharFromCode.char_list_[123] = "F12";
      lol.utils.CharFromCode.char_list_[192] = "`";
      lol.utils.CharFromCode.char_list_[189] = "-";
      lol.utils.CharFromCode.char_list_[187] = "+";
      lol.utils.CharFromCode.char_list_[8] = "Backspace";
      lol.utils.CharFromCode.char_list_[9] = "Tab";
      lol.utils.CharFromCode.char_list_[219] = "[";
      lol.utils.CharFromCode.char_list_[221] = "]";
      lol.utils.CharFromCode.char_list_[220] = "\\";
      lol.utils.CharFromCode.char_list_[20] = "Caps Lock";
      lol.utils.CharFromCode.char_list_[186] = ";";
      lol.utils.CharFromCode.char_list_[222] = "\"";
      lol.utils.CharFromCode.char_list_[16] = "Shift";
      lol.utils.CharFromCode.char_list_[188] = ",";
      lol.utils.CharFromCode.char_list_[190] = ".";
      lol.utils.CharFromCode.char_list_[191] = "/";
      lol.utils.CharFromCode.char_list_[17] = "Ctrl";
      lol.utils.CharFromCode.char_list_[91] = "Win";
      lol.utils.CharFromCode.char_list_[32] = "Space";
      lol.utils.CharFromCode.char_list_[93] = "Context Menu";
      lol.utils.CharFromCode.char_list_[145] = "Scroll Lock";
      lol.utils.CharFromCode.char_list_[19] = "Pause/Break";
      lol.utils.CharFromCode.char_list_[45] = "Insert";
      lol.utils.CharFromCode.char_list_[36] = "Home";
      lol.utils.CharFromCode.char_list_[33] = "Page Up";
      lol.utils.CharFromCode.char_list_[34] = "Page Down";
      lol.utils.CharFromCode.char_list_[35] = "End";
      lol.utils.CharFromCode.char_list_[46] = "Delete";
      lol.utils.CharFromCode.char_list_[37] = "Left";
      lol.utils.CharFromCode.char_list_[38] = "Up";
      lol.utils.CharFromCode.char_list_[39] = "Right";
      lol.utils.CharFromCode.char_list_[40] = "Down";
      lol.utils.CharFromCode.char_list_[144] = "Num Lock";
      lol.utils.CharFromCode.char_list_[111] = "/ Num";
      lol.utils.CharFromCode.char_list_[106] = "* Num";
      lol.utils.CharFromCode.char_list_[109] = "- Num";
      lol.utils.CharFromCode.char_list_[107] = "+ Num";
      lol.utils.CharFromCode.char_list_[110] = ". Num";
      lol.utils.CharFromCode.char_list_[96] = "0 Num";
      lol.utils.CharFromCode.char_list_[97] = "1 Num";
      lol.utils.CharFromCode.char_list_[98] = "2 Num";
      lol.utils.CharFromCode.char_list_[99] = "3 Num";
      lol.utils.CharFromCode.char_list_[100] = "4 Num";
      lol.utils.CharFromCode.char_list_[101] = "5 Num";
      lol.utils.CharFromCode.char_list_[102] = "6 Num";
      lol.utils.CharFromCode.char_list_[103] = "7 Num";
      lol.utils.CharFromCode.char_list_[104] = "8 Num";
      lol.utils.CharFromCode.char_list_[105] = "9 Num";
      lol.utils.CharFromCode.char_list_[13] = "Enter";
   }
   static function getChar(code)
   {
      if(lol.utils.CharFromCode.char_list_ == null)
      {
         lol.utils.CharFromCode.create();
      }
      var _loc1_;
      if(lol.utils.CharFromCode.char_list_[code] != null)
      {
         _loc1_ = lol.utils.CharFromCode.char_list_[code];
      }
      else
      {
         _loc1_ = String.fromCharCode(code);
      }
      return _loc1_;
   }
}
