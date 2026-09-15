class lol.server.mess.CSM_L_Enter extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_L_Enter(accept)
   {
      super();
      this._name = "lenter";
      this.addProp("accept",accept);
   }
}
