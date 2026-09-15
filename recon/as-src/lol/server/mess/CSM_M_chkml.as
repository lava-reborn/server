class lol.server.mess.CSM_M_chkml extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_M_chkml(mode)
   {
      super();
      this._name = "chkml";
      this.addProp("mode",mode);
   }
}
